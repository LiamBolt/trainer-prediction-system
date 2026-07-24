"""Triggers, registry sequences, and constraints Alembic cannot autogenerate.

Everything here is invisible to ``--autogenerate``: triggers, functions, sequences,
and ``EXCLUDE`` constraints. Autogenerate would produce a schema that looks complete
and silently lacks all of it, which is why this revision is hand-written and why §9's
"empty autogenerate diff" check is only meaningful once this has run.

Four things are installed:

1. ``set_updated_at()`` — a shared ``BEFORE UPDATE`` trigger on the 23 tables that
   carry ``updated_at``.
2. ``prevent_audit_mutation()`` — makes ``audit_logs`` append-only in the database
   (D6, FR-13).
3. Registry sequences and ``next_registry_number()`` (§5.9).
4. A deferred constraint trigger asserting that a scoring policy's weights sum to
   100, plus a GiST ``EXCLUDE`` preventing overlapping unavailability windows.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-23

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Every table carrying ``updated_at``. Excluded by design: ``audit_logs`` (append-only,
#: so the column would be a lie), ``predictions`` and ``prediction_exclusions`` (both
#: immutable statements about a single moment).
TABLES_WITH_UPDATED_AT: tuple[str, ...] = (
    "roles",
    "police_ranks",
    "directorates",
    "regions",
    "stations",
    "specialization_areas",
    "training_categories",
    "institutions",
    "qualification_levels",
    "proficiency_levels",
    "users",
    "refresh_tokens",
    "trainers",
    "trainer_qualifications",
    "trainer_specializations",
    "trainer_unavailability",
    "training_programmes",
    "scoring_policies",
    "scoring_policy_weights",
    "prediction_runs",
    "allocations",
    "performance_evaluations",
    "notifications",
)

REGISTRY_SEQUENCES: tuple[tuple[str, str], ...] = (
    ("REQ", "registry_req_seq"),
    ("ALL", "registry_all_seq"),
    ("EVL", "registry_evl_seq"),
)


def upgrade() -> None:
    """Install the functions, triggers, sequences, and extra constraints."""
    # -- 1. Shared updated_at trigger ---------------------------------------
    # A trigger, not SQLAlchemy's onupdate: a trigger cannot be bypassed by a bulk
    # UPDATE, a raw text() statement, or a DBA at a psql prompt. onupdate can be
    # bypassed by all three, which makes it a convention rather than a guarantee.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION set_updated_at() IS "
        "'Sets updated_at to now() on every UPDATE. Applied to all tables carrying the column.';"
    )
    for table in TABLES_WITH_UPDATED_AT:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_set_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )

    # -- 2. Audit immutability (D6, FR-13) ----------------------------------
    # FR-13 says audit entries cannot be edited or deleted *by any role*. Enforcing
    # that in the service layer would leave it one ORM call, one migration, or one
    # psql session away from being untrue. Here, the only way past it is to drop the
    # trigger — which is itself a schema change, visible in a migration diff.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_logs is append-only: % is not permitted (FR-13)', TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION prevent_audit_mutation() IS "
        "'Raises on UPDATE or DELETE against audit_logs. Enforces FR-13 below the application.';"
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();
        """
    )

    # -- 3. Registry numbers (§5.9) -----------------------------------------
    # A sequence, never MAX(id)+1. Under two concurrent approvals MAX+1 returns the
    # same value twice, and a duplicate registry number on a government allocation
    # record is a serious defect. Sequences are concurrency-safe.
    #
    # Gaps are expected: a sequence does not roll back with its transaction. A
    # registry number is an identifier, not a count, so gaps carry no meaning and
    # must not be "fixed" — doing so would renumber issued documents.
    for _family, sequence in REGISTRY_SEQUENCES:
        op.execute(f"CREATE SEQUENCE {sequence} START WITH 1 INCREMENT BY 1 NO CYCLE;")
        op.execute(
            f"COMMENT ON SEQUENCE {sequence} IS "
            f"'Registry counter. Gaps after a rollback are expected and must not be repaired.';"
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION next_registry_number(family text) RETURNS varchar
        LANGUAGE plpgsql AS $$
        DECLARE
            sequence_name text;
            counter       bigint;
        BEGIN
            sequence_name := CASE family
                WHEN 'REQ' THEN 'registry_req_seq'
                WHEN 'ALL' THEN 'registry_all_seq'
                WHEN 'EVL' THEN 'registry_evl_seq'
                ELSE NULL
            END;

            IF sequence_name IS NULL THEN
                RAISE EXCEPTION 'Unknown registry family: %. Expected REQ, ALL, or EVL.', family;
            END IF;

            counter := nextval(sequence_name);
            RETURN 'TPS/' || family || '/' || to_char(now(), 'YYYY') || '/'
                   || lpad(counter::text, 4, '0');
        END;
        $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION next_registry_number(text) IS "
        "'Returns TPS/{FAMILY}/{YYYY}/{NNNN}. Families: REQ, ALL, EVL. Concurrency-safe.';"
    )

    # -- 4a. Scoring weights must sum to 100 --------------------------------
    # This cannot be a row-level CHECK, which sees only its own row. A DEFERRABLE
    # INITIALLY DEFERRED constraint trigger fires at COMMIT, by which point all five
    # weight rows exist — so a transaction inserting a whole policy is valid
    # throughout and only checked once, at the end.
    #
    # A total of exactly 0 is permitted: that is a policy whose weights have not been
    # inserted yet, or one whose rows were removed by CASCADE when the policy itself
    # was deleted. See ADR-0011 for exactly what this does and does not guarantee.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_policy_weights_sum() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            target_policy bigint;
            total         numeric;
        BEGIN
            target_policy := COALESCE(NEW.policy_id, OLD.policy_id);

            SELECT COALESCE(SUM(weight), 0) INTO total
            FROM scoring_policy_weights
            WHERE policy_id = target_policy;

            IF total <> 0 AND total <> 100 THEN
                RAISE EXCEPTION
                    'Scoring policy % has weights summing to %; they must sum to 100 (NFR-10).',
                    target_policy, total
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION check_policy_weights_sum() IS "
        "'Deferred check that a policy''s criterion weights total 100. Fires at COMMIT.';"
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_scoring_policy_weights_sum
        AFTER INSERT OR UPDATE OR DELETE ON scoring_policy_weights
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION check_policy_weights_sum();
        """
    )

    # -- 4b. No overlapping unavailability windows --------------------------
    # A trainer cannot be on leave and in court at the same time, and an overlap
    # would double-count against BR-03. btree_gist supplies the integer equality
    # operator that lets trainer_id join the date range in one GiST index.
    op.execute(
        """
        ALTER TABLE trainer_unavailability
        ADD CONSTRAINT ex_trainer_unavailability_no_overlap
        EXCLUDE USING gist (
            trainer_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
        );
        """
    )
    op.execute(
        "COMMENT ON CONSTRAINT ex_trainer_unavailability_no_overlap ON trainer_unavailability IS "
        "'One trainer''s absence windows may not overlap. Inclusive of both end dates.';"
    )


def downgrade() -> None:
    """Remove everything installed by :func:`upgrade`, in reverse dependency order."""
    op.execute(
        "ALTER TABLE trainer_unavailability "
        "DROP CONSTRAINT IF EXISTS ex_trainer_unavailability_no_overlap;"
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_scoring_policy_weights_sum ON scoring_policy_weights;"
    )
    op.execute("DROP FUNCTION IF EXISTS check_policy_weights_sum();")

    op.execute("DROP FUNCTION IF EXISTS next_registry_number(text);")
    for _family, sequence in REGISTRY_SEQUENCES:
        op.execute(f"DROP SEQUENCE IF EXISTS {sequence};")

    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_mutation();")

    for table in TABLES_WITH_UPDATED_AT:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_set_updated_at ON {table};")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
