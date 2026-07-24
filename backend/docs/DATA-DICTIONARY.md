# TPS Data Dictionary

> **Generated file — do not edit by hand.** Produced by `python -m scripts.gen_data_dictionary`, read directly from the live database via `information_schema` and `pg_description`.
>
> Database `tps_db` · generated 2026-07-23 09:41 UTC

Every description below originates as a `comment=` on a SQLAlchemy column or table in `app/models/`, which Alembic writes into `pg_description`. The models are the single source of truth (D1); this document is a projection of them, taken from the database rather than from the code, so it reflects what was actually migrated.

**26 tables · 1 view**

## Contents

- [`allocations`](#allocations) — table
- [`audit_logs`](#audit-logs) — table
- [`directorates`](#directorates) — table
- [`institutions`](#institutions) — table
- [`notifications`](#notifications) — table
- [`performance_evaluations`](#performance-evaluations) — table
- [`police_ranks`](#police-ranks) — table
- [`prediction_exclusions`](#prediction-exclusions) — table
- [`prediction_runs`](#prediction-runs) — table
- [`predictions`](#predictions) — table
- [`proficiency_levels`](#proficiency-levels) — table
- [`qualification_levels`](#qualification-levels) — table
- [`refresh_tokens`](#refresh-tokens) — table
- [`regions`](#regions) — table
- [`roles`](#roles) — table
- [`scoring_policies`](#scoring-policies) — table
- [`scoring_policy_weights`](#scoring-policy-weights) — table
- [`specialization_areas`](#specialization-areas) — table
- [`stations`](#stations) — table
- [`trainer_qualifications`](#trainer-qualifications) — table
- [`trainer_specializations`](#trainer-specializations) — table
- [`trainer_unavailability`](#trainer-unavailability) — table
- [`trainers`](#trainers) — table
- [`training_categories`](#training-categories) — table
- [`training_programmes`](#training-programmes) — table
- [`users`](#users) — table
- [`v_trainer_scoring_facts`](#v-trainer-scoring-facts) — view

---

## allocations

*Table.* Approved trainer assignments with a frozen decision snapshot. FR-08, FR-09.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `allocation_id` | `bigint` | NOT NULL | identity |  |
| `registry_number` | `character varying(32)` | NOT NULL | — | e.g. 'TPS/ALL/2026/0417'. From next_registry_number('ALL'). |
| `prediction_id` | `bigint` | NOT NULL | — | D7: UNIQUE gives one-to-zero-or-one. One prediction, at most one allocation. |
| `programme_id` | `bigint` | NOT NULL | — |  |
| `trainer_id` | `bigint` | NOT NULL | — |  |
| `approved_by_user_id` | `bigint` | NOT NULL | — | The Training Administrator accountable for this decision. |
| `status` | `character varying(24)` | NOT NULL | — |  |
| `approval_date` | `timestamp with time zone` | NOT NULL | now() |  |
| `remarks` | `text` | NULL | — | Administrator's note. NULL when none was given. |
| `frozen_score` | `numeric(5,2)` | NOT NULL | — | prediction_score as it stood at approval. |
| `frozen_rank_position` | `integer` | NOT NULL | — | rank_position as it stood at approval. |
| `frozen_breakdown` | `jsonb` | NOT NULL | — | CriterionScore[] as shown on the Decision Receipt. |
| `frozen_weights` | `jsonb` | NOT NULL | — | The weights in force at approval. |
| `frozen_rationale` | `text` | NOT NULL | — | The rationale as it stood at approval — this is the text shown to the trainer. |
| `weights_were_simulated` | `boolean` | NOT NULL | false | True when approved against Weight Studio weights rather than the active policy. |
| `decline_reason` | `text` | NULL | — | Required when status = DECLINED, enforced by CHECK (FR-09). |
| `declined_at` | `timestamp with time zone` | NULL | — |  |
| `responded_at` | `timestamp with time zone` | NULL | — | When the trainer answered. NULL means still awaiting a response. |
| `superseded_by_allocation_id` | `bigint` | NULL | — | Set when a decline promotes the next candidate, linking the chain of decisions. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_allocations_declined_requires_reason` | b'c' | `CHECK ((((status)::text <> 'DECLINED'::text) OR (decline_reason IS NOT NULL)))` |
| `ck_allocations_declined_requires_timestamp` | b'c' | `CHECK ((((status)::text <> 'DECLINED'::text) OR (declined_at IS NOT NULL)))` |
| `ck_allocations_frozen_rank_position_positive` | b'c' | `CHECK ((frozen_rank_position > 0))` |
| `ck_allocations_frozen_score_range` | b'c' | `CHECK (((frozen_score >= (0)::numeric) AND (frozen_score <= (100)::numeric)))` |
| `ck_allocations_status_valid` | b'c' | `CHECK (((status)::text = ANY ((ARRAY['PENDING_TRAINER'::character varying, 'CONFIRMED'::character varying, 'DECLINED'::character varying, 'CONDUCTED'::character varying, 'EVALUATED'::character varying, 'WITHDRAWN'::character varying])::text[])))` |
| `fk_allocations_approved_by_user_id_users` | b'f' | `FOREIGN KEY (approved_by_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `fk_allocations_prediction_id_predictions` | b'f' | `FOREIGN KEY (prediction_id) REFERENCES predictions(prediction_id) ON DELETE RESTRICT` |
| `fk_allocations_programme_id_training_programmes` | b'f' | `FOREIGN KEY (programme_id) REFERENCES training_programmes(programme_id) ON DELETE RESTRICT` |
| `fk_allocations_superseded_by_allocation_id_allocations` | b'f' | `FOREIGN KEY (superseded_by_allocation_id) REFERENCES allocations(allocation_id) ON DELETE RESTRICT` |
| `fk_allocations_trainer_id_trainers` | b'f' | `FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE RESTRICT` |
| `allocations_allocation_id_not_null` | b'n' | `NOT NULL allocation_id` |
| `allocations_approval_date_not_null` | b'n' | `NOT NULL approval_date` |
| `allocations_approved_by_user_id_not_null` | b'n' | `NOT NULL approved_by_user_id` |
| `allocations_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `allocations_frozen_breakdown_not_null` | b'n' | `NOT NULL frozen_breakdown` |
| `allocations_frozen_rank_position_not_null` | b'n' | `NOT NULL frozen_rank_position` |
| `allocations_frozen_rationale_not_null` | b'n' | `NOT NULL frozen_rationale` |
| `allocations_frozen_score_not_null` | b'n' | `NOT NULL frozen_score` |
| `allocations_frozen_weights_not_null` | b'n' | `NOT NULL frozen_weights` |
| `allocations_prediction_id_not_null` | b'n' | `NOT NULL prediction_id` |
| `allocations_programme_id_not_null` | b'n' | `NOT NULL programme_id` |
| `allocations_registry_number_not_null` | b'n' | `NOT NULL registry_number` |
| `allocations_status_not_null` | b'n' | `NOT NULL status` |
| `allocations_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `allocations_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `allocations_weights_were_simulated_not_null` | b'n' | `NOT NULL weights_were_simulated` |
| `pk_allocations` | b'p' | `PRIMARY KEY (allocation_id)` |
| `uq_allocations_prediction_id` | b'u' | `UNIQUE (prediction_id)` |
| `uq_allocations_registry_number` | b'u' | `UNIQUE (registry_number)` |

**Indexes**

- `ix_allocations_approved_by_user_id` — `CREATE INDEX ix_allocations_approved_by_user_id ON public.allocations USING btree (approved_by_user_id)`
- `ix_allocations_programme_id` — `CREATE INDEX ix_allocations_programme_id ON public.allocations USING btree (programme_id)`
- `ix_allocations_status` — `CREATE INDEX ix_allocations_status ON public.allocations USING btree (status)`
- `ix_allocations_superseded_by_allocation_id` — `CREATE INDEX ix_allocations_superseded_by_allocation_id ON public.allocations USING btree (superseded_by_allocation_id)`
- `ix_allocations_trainer_approval_date` — `CREATE INDEX ix_allocations_trainer_approval_date ON public.allocations USING btree (trainer_id, approval_date)`
- `ix_allocations_trainer_id` — `CREATE INDEX ix_allocations_trainer_id ON public.allocations USING btree (trainer_id)`
- `pk_allocations` — `CREATE UNIQUE INDEX pk_allocations ON public.allocations USING btree (allocation_id)`
- `uq_allocations_prediction_id` — `CREATE UNIQUE INDEX uq_allocations_prediction_id ON public.allocations USING btree (prediction_id)`
- `uq_allocations_registry_number` — `CREATE UNIQUE INDEX uq_allocations_registry_number ON public.allocations USING btree (registry_number)`

---

## audit_logs

*Table.* Append-only audit trail (FR-13). UPDATE and DELETE raise an exception via the prevent_audit_mutation trigger.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `log_id` | `bigint` | NOT NULL | identity |  |
| `actor_user_id` | `bigint` | NULL | — | Who acted. NULL for system actions and for failed sign-ins with an unknown username. |
| `actor_role` | `character varying(40)` | NULL | — | The actor's role at the time of the action. Denormalised on purpose. |
| `action` | `character varying(60)` | NOT NULL | — |  |
| `entity_type` | `character varying(60)` | NULL | — | e.g. 'ALLOCATION'. NULL for session-level actions. |
| `entity_id` | `bigint` | NULL | — | Affected row id. NULL for session-level actions. |
| `before_json` | `jsonb` | NULL | — | Prior state. NULL for creations and for read actions. |
| `after_json` | `jsonb` | NULL | — | Resulting state. NULL for deletions and for read actions. |
| `detail` | `text` | NULL | — | Human-readable summary shown in the audit viewer. |
| `ip_address` | `inet` | NULL | — |  |
| `user_agent` | `character varying(255)` | NULL | — |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() |  |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_audit_logs_action_valid` | b'c' | `CHECK (((action)::text = ANY ((ARRAY['LOGIN_SUCCESS'::character varying, 'LOGIN_FAILED'::character varying, 'ACCOUNT_LOCKED'::character varying, 'LOGOUT'::character varying, 'TOKEN_REFRESHED'::character varying, 'PROGRAMME_CREATED'::character varying, 'REQUIREMENTS_DEFINED'::character varying, 'REQUIREMENTS_CHANGED'::character varying, 'PREDICTION_GENERATED'::character varying, 'WEIGHTS_SIMULATED'::character varying, 'WEIGHTS_SAVED'::character varying, 'ALLOCATION_APPROVED'::character varying, 'ALLOCATION_DECLINED'::character varying, 'CANDIDATE_SKIPPED'::character varying, 'ASSIGNMENT_ACCEPTED'::character varying, 'ASSIGNMENT_DECLINED'::character varying, 'EVALUATION_RECORDED'::character varying, 'REPORT_EXPORTED'::character varying, 'USER_CREATED'::character varying, 'USER_MODIFIED'::character varying, 'USER_DEACTIVATED'::character varying, 'ROLE_CHANGED'::character varying, 'PROFILE_UPDATED'::character varying, 'AVAILABILITY_CHANGED'::character varying, 'UNAUTHORISED_ATTEMPT'::character varying])::text[])))` |
| `fk_audit_logs_actor_user_id_users` | b'f' | `FOREIGN KEY (actor_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `audit_logs_action_not_null` | b'n' | `NOT NULL action` |
| `audit_logs_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `audit_logs_log_id_not_null` | b'n' | `NOT NULL log_id` |
| `pk_audit_logs` | b'p' | `PRIMARY KEY (log_id)` |

**Indexes**

- `ix_audit_logs_action` — `CREATE INDEX ix_audit_logs_action ON public.audit_logs USING btree (action)`
- `ix_audit_logs_actor_user_id` — `CREATE INDEX ix_audit_logs_actor_user_id ON public.audit_logs USING btree (actor_user_id)`
- `ix_audit_logs_created_at` — `CREATE INDEX ix_audit_logs_created_at ON public.audit_logs USING btree (created_at)`
- `ix_audit_logs_entity` — `CREATE INDEX ix_audit_logs_entity ON public.audit_logs USING btree (entity_type, entity_id)`
- `pk_audit_logs` — `CREATE UNIQUE INDEX pk_audit_logs ON public.audit_logs USING btree (log_id)`

---

## directorates

*Table.* The 17 UPF directorates.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `directorate_id` | `bigint` | NOT NULL | identity |  |
| `name` | `character varying(120)` | NOT NULL | — |  |
| `abbreviation` | `character varying(16)` | NULL | — | e.g. 'CID'. NULL where the UPF uses no abbreviation. |
| `is_training_authority` | `boolean` | NOT NULL | false | True only for Human Resource Development — the directorate that owns training. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `directorates_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `directorates_directorate_id_not_null` | b'n' | `NOT NULL directorate_id` |
| `directorates_is_training_authority_not_null` | b'n' | `NOT NULL is_training_authority` |
| `directorates_name_not_null` | b'n' | `NOT NULL name` |
| `directorates_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_directorates` | b'p' | `PRIMARY KEY (directorate_id)` |
| `uq_directorates_name` | b'u' | `UNIQUE (name)` |

**Indexes**

- `pk_directorates` — `CREATE UNIQUE INDEX pk_directorates ON public.directorates USING btree (directorate_id)`
- `uq_directorates_name` — `CREATE UNIQUE INDEX uq_directorates_name ON public.directorates USING btree (name)`

---

## institutions

*Table.* Awarding institutions for trainer qualifications.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `institution_id` | `bigint` | NOT NULL | identity |  |
| `name` | `character varying(160)` | NOT NULL | — |  |
| `institution_type` | `character varying(24)` | NOT NULL | — | POLICE, UNIVERSITY, PROFESSIONAL, or INTERNATIONAL. POLICE earns a scoring bonus. |
| `country` | `character varying(60)` | NOT NULL | 'Uganda'::character varying |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_institutions_institution_type_valid` | b'c' | `CHECK (((institution_type)::text = ANY ((ARRAY['POLICE'::character varying, 'UNIVERSITY'::character varying, 'PROFESSIONAL'::character varying, 'INTERNATIONAL'::character varying])::text[])))` |
| `institutions_country_not_null` | b'n' | `NOT NULL country` |
| `institutions_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `institutions_institution_id_not_null` | b'n' | `NOT NULL institution_id` |
| `institutions_institution_type_not_null` | b'n' | `NOT NULL institution_type` |
| `institutions_name_not_null` | b'n' | `NOT NULL name` |
| `institutions_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_institutions` | b'p' | `PRIMARY KEY (institution_id)` |
| `uq_institutions_name` | b'u' | `UNIQUE (name)` |

**Indexes**

- `ix_institutions_institution_type` — `CREATE INDEX ix_institutions_institution_type ON public.institutions USING btree (institution_type)`
- `pk_institutions` — `CREATE UNIQUE INDEX pk_institutions ON public.institutions USING btree (institution_id)`
- `uq_institutions_name` — `CREATE UNIQUE INDEX uq_institutions_name ON public.institutions USING btree (name)`

---

## notifications

*Table.* In-app notifications. FR-11.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `notification_id` | `bigint` | NOT NULL | identity |  |
| `recipient_user_id` | `bigint` | NOT NULL | — | CASCADE: a deleted user's notifications have no recipient and no meaning. |
| `message` | `text` | NOT NULL | — |  |
| `type` | `character varying(20)` | NOT NULL | — |  |
| `link_to` | `character varying(255)` | NULL | — | In-app route, e.g. '/my-assignments'. NULL when there is nowhere to go. |
| `status` | `character varying(10)` | NOT NULL | 'UNREAD'::character varying |  |
| `delivery_status` | `character varying(20)` | NOT NULL | 'PENDING'::character varying |  |
| `sent_date` | `timestamp with time zone` | NULL | — | NULL while delivery_status is PENDING. |
| `read_at` | `timestamp with time zone` | NULL | — | NULL while unread. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_notifications_delivery_status_valid` | b'c' | `CHECK (((delivery_status)::text = ANY ((ARRAY['PENDING'::character varying, 'SENT'::character varying, 'FAILED'::character varying])::text[])))` |
| `ck_notifications_read_requires_timestamp` | b'c' | `CHECK ((((status)::text <> 'READ'::text) OR (read_at IS NOT NULL)))` |
| `ck_notifications_status_valid` | b'c' | `CHECK (((status)::text = ANY ((ARRAY['UNREAD'::character varying, 'READ'::character varying])::text[])))` |
| `ck_notifications_type_valid` | b'c' | `CHECK (((type)::text = ANY ((ARRAY['ASSIGNMENT'::character varying, 'APPROVAL'::character varying, 'EVALUATION'::character varying, 'SYSTEM'::character varying, 'REMINDER'::character varying])::text[])))` |
| `fk_notifications_recipient_user_id_users` | b'f' | `FOREIGN KEY (recipient_user_id) REFERENCES users(user_id) ON DELETE CASCADE` |
| `notifications_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `notifications_delivery_status_not_null` | b'n' | `NOT NULL delivery_status` |
| `notifications_message_not_null` | b'n' | `NOT NULL message` |
| `notifications_notification_id_not_null` | b'n' | `NOT NULL notification_id` |
| `notifications_recipient_user_id_not_null` | b'n' | `NOT NULL recipient_user_id` |
| `notifications_status_not_null` | b'n' | `NOT NULL status` |
| `notifications_type_not_null` | b'n' | `NOT NULL type` |
| `notifications_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_notifications` | b'p' | `PRIMARY KEY (notification_id)` |

**Indexes**

- `ix_notifications_recipient_status_created` — `CREATE INDEX ix_notifications_recipient_status_created ON public.notifications USING btree (recipient_user_id, status, created_at)`
- `pk_notifications` — `CREATE UNIQUE INDEX pk_notifications ON public.notifications USING btree (notification_id)`

---

## performance_evaluations

*Table.* Post-course trainer ratings. Read on every prediction run. FR-10.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `evaluation_id` | `bigint` | NOT NULL | identity |  |
| `registry_number` | `character varying(32)` | NOT NULL | — | e.g. 'TPS/EVL/2026/0088'. From next_registry_number('EVL'). |
| `allocation_id` | `bigint` | NOT NULL | — | One evaluation per allocation. UNIQUE makes double-rating impossible. |
| `trainer_id` | `bigint` | NOT NULL | — | Denormalised from the allocation. See class docstring. |
| `programme_id` | `bigint` | NOT NULL | — | Denormalised from the allocation. Drives the relevance test. |
| `score_awarded` | `numeric(2,1)` | NOT NULL | — | 1.0 to 5.0, one decimal place. NUMERIC, never float (D4). |
| `evaluator_comments` | `text` | NOT NULL | — | Required: a bare number is not an evaluation. |
| `evaluated_by_user_id` | `bigint` | NOT NULL | — |  |
| `evaluation_date` | `date` | NOT NULL | — | Date of assessment, which may precede the record's creation. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_performance_evaluations_score_awarded_range` | b'c' | `CHECK (((score_awarded >= 1.0) AND (score_awarded <= 5.0)))` |
| `fk_performance_evaluations_allocation_id_allocations` | b'f' | `FOREIGN KEY (allocation_id) REFERENCES allocations(allocation_id) ON DELETE RESTRICT` |
| `fk_performance_evaluations_evaluated_by_user_id_users` | b'f' | `FOREIGN KEY (evaluated_by_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `fk_performance_evaluations_programme_id_training_programmes` | b'f' | `FOREIGN KEY (programme_id) REFERENCES training_programmes(programme_id) ON DELETE RESTRICT` |
| `fk_performance_evaluations_trainer_id_trainers` | b'f' | `FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE RESTRICT` |
| `performance_evaluations_allocation_id_not_null` | b'n' | `NOT NULL allocation_id` |
| `performance_evaluations_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `performance_evaluations_evaluated_by_user_id_not_null` | b'n' | `NOT NULL evaluated_by_user_id` |
| `performance_evaluations_evaluation_date_not_null` | b'n' | `NOT NULL evaluation_date` |
| `performance_evaluations_evaluation_id_not_null` | b'n' | `NOT NULL evaluation_id` |
| `performance_evaluations_evaluator_comments_not_null` | b'n' | `NOT NULL evaluator_comments` |
| `performance_evaluations_programme_id_not_null` | b'n' | `NOT NULL programme_id` |
| `performance_evaluations_registry_number_not_null` | b'n' | `NOT NULL registry_number` |
| `performance_evaluations_score_awarded_not_null` | b'n' | `NOT NULL score_awarded` |
| `performance_evaluations_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `performance_evaluations_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_performance_evaluations` | b'p' | `PRIMARY KEY (evaluation_id)` |
| `uq_performance_evaluations_allocation_id` | b'u' | `UNIQUE (allocation_id)` |
| `uq_performance_evaluations_registry_number` | b'u' | `UNIQUE (registry_number)` |

**Indexes**

- `ix_performance_evaluations_evaluated_by_user_id` — `CREATE INDEX ix_performance_evaluations_evaluated_by_user_id ON public.performance_evaluations USING btree (evaluated_by_user_id)`
- `ix_performance_evaluations_programme_id` — `CREATE INDEX ix_performance_evaluations_programme_id ON public.performance_evaluations USING btree (programme_id)`
- `ix_performance_evaluations_trainer_date` — `CREATE INDEX ix_performance_evaluations_trainer_date ON public.performance_evaluations USING btree (trainer_id, evaluation_date)`
- `pk_performance_evaluations` — `CREATE UNIQUE INDEX pk_performance_evaluations ON public.performance_evaluations USING btree (evaluation_id)`
- `uq_performance_evaluations_allocation_id` — `CREATE UNIQUE INDEX uq_performance_evaluations_allocation_id ON public.performance_evaluations USING btree (allocation_id)`
- `uq_performance_evaluations_registry_number` — `CREATE UNIQUE INDEX uq_performance_evaluations_registry_number ON public.performance_evaluations USING btree (registry_number)`

---

## police_ranks

*Table.* The UPF rank ladder, seeded from the official structure.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `rank_id` | `bigint` | NOT NULL | identity |  |
| `code` | `character varying(8)` | NOT NULL | — | Short code, e.g. 'ASP'. |
| `full_name` | `character varying(80)` | NOT NULL | — | e.g. 'Assistant Superintendent of Police'. |
| `management_level` | `character varying(24)` | NOT NULL | — | Band: STRATEGIC, SENIOR, MIDDLE, or JUNIOR. |
| `seniority_order` | `smallint` | NOT NULL | — | 1 = most junior (SPC), 15 = most senior (IGP). The orderable key. |
| `typical_appointments` | `text` | NULL | — | Posts the UPF attaches to this rank. Guides plausible seed data (§7.2). |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_police_ranks_management_level_valid` | b'c' | `CHECK (((management_level)::text = ANY ((ARRAY['STRATEGIC'::character varying, 'SENIOR'::character varying, 'MIDDLE'::character varying, 'JUNIOR'::character varying])::text[])))` |
| `ck_police_ranks_seniority_order_positive` | b'c' | `CHECK ((seniority_order > 0))` |
| `police_ranks_code_not_null` | b'n' | `NOT NULL code` |
| `police_ranks_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `police_ranks_full_name_not_null` | b'n' | `NOT NULL full_name` |
| `police_ranks_management_level_not_null` | b'n' | `NOT NULL management_level` |
| `police_ranks_rank_id_not_null` | b'n' | `NOT NULL rank_id` |
| `police_ranks_seniority_order_not_null` | b'n' | `NOT NULL seniority_order` |
| `police_ranks_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_police_ranks` | b'p' | `PRIMARY KEY (rank_id)` |
| `uq_police_ranks_code` | b'u' | `UNIQUE (code)` |
| `uq_police_ranks_seniority_order` | b'u' | `UNIQUE (seniority_order)` |

**Indexes**

- `pk_police_ranks` — `CREATE UNIQUE INDEX pk_police_ranks ON public.police_ranks USING btree (rank_id)`
- `uq_police_ranks_code` — `CREATE UNIQUE INDEX uq_police_ranks_code ON public.police_ranks USING btree (code)`
- `uq_police_ranks_seniority_order` — `CREATE UNIQUE INDEX uq_police_ranks_seniority_order ON public.police_ranks USING btree (seniority_order)`

---

## prediction_exclusions

*Table.* The Exclusion Ledger: every gated-out trainer, and the rule that gated them.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `exclusion_id` | `bigint` | NOT NULL | identity |  |
| `run_id` | `bigint` | NOT NULL | — |  |
| `trainer_id` | `bigint` | NOT NULL | — |  |
| `reason` | `character varying(40)` | NOT NULL | — | Machine reason, one of ExclusionReason. |
| `reason_detail` | `character varying(300)` | NOT NULL | — | Human sentence, e.g. 'Assigned to Digital Forensics Level 2 - 10-21 Aug 2026'. |
| `business_rule` | `character varying(10)` | NOT NULL | — | Rule citation: BR-03, BR-04, or FR-05. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() |  |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_prediction_exclusions_business_rule_valid` | b'c' | `CHECK (((business_rule)::text = ANY ((ARRAY['BR-03'::character varying, 'BR-04'::character varying, 'FR-05'::character varying])::text[])))` |
| `ck_prediction_exclusions_reason_valid` | b'c' | `CHECK (((reason)::text = ANY ((ARRAY['UNAVAILABLE'::character varying, 'MISSING_SPECIALIZATION'::character varying, 'BELOW_MINIMUM_EXPERIENCE'::character varying, 'BELOW_MINIMUM_QUALIFICATION'::character varying, 'SCHEDULE_CONFLICT'::character varying])::text[])))` |
| `fk_prediction_exclusions_run_id_prediction_runs` | b'f' | `FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id) ON DELETE CASCADE` |
| `fk_prediction_exclusions_trainer_id_trainers` | b'f' | `FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE RESTRICT` |
| `prediction_exclusions_business_rule_not_null` | b'n' | `NOT NULL business_rule` |
| `prediction_exclusions_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `prediction_exclusions_exclusion_id_not_null` | b'n' | `NOT NULL exclusion_id` |
| `prediction_exclusions_reason_detail_not_null` | b'n' | `NOT NULL reason_detail` |
| `prediction_exclusions_reason_not_null` | b'n' | `NOT NULL reason` |
| `prediction_exclusions_run_id_not_null` | b'n' | `NOT NULL run_id` |
| `prediction_exclusions_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `pk_prediction_exclusions` | b'p' | `PRIMARY KEY (exclusion_id)` |
| `uq_prediction_exclusions_run_id_trainer_id` | b'u' | `UNIQUE (run_id, trainer_id)` |

**Indexes**

- `ix_prediction_exclusions_run_reason` — `CREATE INDEX ix_prediction_exclusions_run_reason ON public.prediction_exclusions USING btree (run_id, reason)`
- `ix_prediction_exclusions_trainer_id` — `CREATE INDEX ix_prediction_exclusions_trainer_id ON public.prediction_exclusions USING btree (trainer_id)`
- `pk_prediction_exclusions` — `CREATE UNIQUE INDEX pk_prediction_exclusions ON public.prediction_exclusions USING btree (exclusion_id)`
- `uq_prediction_exclusions_run_id_trainer_id` — `CREATE UNIQUE INDEX uq_prediction_exclusions_run_id_trainer_id ON public.prediction_exclusions USING btree (run_id, trainer_id)`

---

## prediction_runs

*Table.* One row per prediction engine execution. Superseded, never deleted.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `run_id` | `bigint` | NOT NULL | identity |  |
| `programme_id` | `bigint` | NOT NULL | — |  |
| `policy_id` | `bigint` | NULL | — | NULL when run with ad-hoc simulated weights rather than a saved policy. |
| `weights_snapshot` | `jsonb` | NOT NULL | — | The exact weights used, frozen. Never re-read from scoring_policies. |
| `weights_are_policy_default` | `boolean` | NOT NULL | true | False when the Administrator simulated weights in the Weight Studio. |
| `candidate_pool_size` | `integer` | NOT NULL | — | Trainers considered before any gate was applied. |
| `excluded_count` | `integer` | NOT NULL | — | Trainers removed by the BR-03/BR-04/FR-05 gates. |
| `ranked_count` | `integer` | NOT NULL | — | Trainers that passed every gate and were scored. |
| `elapsed_ms` | `integer` | NOT NULL | — | Wall-clock duration. NFR-01: measured on every run. |
| `is_superseded` | `boolean` | NOT NULL | false | Set when a later run replaces this one. The row itself is never deleted. |
| `generated_by_user_id` | `bigint` | NOT NULL | — |  |
| `generated_at` | `timestamp with time zone` | NOT NULL | now() |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_prediction_runs_candidate_pool_size_non_negative` | b'c' | `CHECK ((candidate_pool_size >= 0))` |
| `ck_prediction_runs_counts_within_pool` | b'c' | `CHECK (((excluded_count + ranked_count) <= candidate_pool_size))` |
| `ck_prediction_runs_elapsed_ms_non_negative` | b'c' | `CHECK ((elapsed_ms >= 0))` |
| `ck_prediction_runs_excluded_count_non_negative` | b'c' | `CHECK ((excluded_count >= 0))` |
| `ck_prediction_runs_ranked_count_non_negative` | b'c' | `CHECK ((ranked_count >= 0))` |
| `fk_prediction_runs_generated_by_user_id_users` | b'f' | `FOREIGN KEY (generated_by_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `fk_prediction_runs_policy_id_scoring_policies` | b'f' | `FOREIGN KEY (policy_id) REFERENCES scoring_policies(policy_id) ON DELETE RESTRICT` |
| `fk_prediction_runs_programme_id_training_programmes` | b'f' | `FOREIGN KEY (programme_id) REFERENCES training_programmes(programme_id) ON DELETE CASCADE` |
| `prediction_runs_candidate_pool_size_not_null` | b'n' | `NOT NULL candidate_pool_size` |
| `prediction_runs_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `prediction_runs_elapsed_ms_not_null` | b'n' | `NOT NULL elapsed_ms` |
| `prediction_runs_excluded_count_not_null` | b'n' | `NOT NULL excluded_count` |
| `prediction_runs_generated_at_not_null` | b'n' | `NOT NULL generated_at` |
| `prediction_runs_generated_by_user_id_not_null` | b'n' | `NOT NULL generated_by_user_id` |
| `prediction_runs_is_superseded_not_null` | b'n' | `NOT NULL is_superseded` |
| `prediction_runs_programme_id_not_null` | b'n' | `NOT NULL programme_id` |
| `prediction_runs_ranked_count_not_null` | b'n' | `NOT NULL ranked_count` |
| `prediction_runs_run_id_not_null` | b'n' | `NOT NULL run_id` |
| `prediction_runs_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `prediction_runs_weights_are_policy_default_not_null` | b'n' | `NOT NULL weights_are_policy_default` |
| `prediction_runs_weights_snapshot_not_null` | b'n' | `NOT NULL weights_snapshot` |
| `pk_prediction_runs` | b'p' | `PRIMARY KEY (run_id)` |

**Indexes**

- `ix_prediction_runs_generated_at` — `CREATE INDEX ix_prediction_runs_generated_at ON public.prediction_runs USING btree (generated_at)`
- `ix_prediction_runs_generated_by_user_id` — `CREATE INDEX ix_prediction_runs_generated_by_user_id ON public.prediction_runs USING btree (generated_by_user_id)`
- `ix_prediction_runs_policy_id` — `CREATE INDEX ix_prediction_runs_policy_id ON public.prediction_runs USING btree (policy_id)`
- `ix_prediction_runs_programme_generated` — `CREATE INDEX ix_prediction_runs_programme_generated ON public.prediction_runs USING btree (programme_id, generated_at)`
- `pk_prediction_runs` — `CREATE UNIQUE INDEX pk_prediction_runs ON public.prediction_runs USING btree (run_id)`

---

## predictions

*Table.* A trainer's score and rank within a run. Immutable; no updated_at.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `prediction_id` | `bigint` | NOT NULL | identity |  |
| `run_id` | `bigint` | NOT NULL | — |  |
| `programme_id` | `bigint` | NOT NULL | — | Denormalised from the run so programme-scoped queries skip a join. |
| `trainer_id` | `bigint` | NOT NULL | — | RESTRICT: a scored trainer forms part of a decision record. |
| `prediction_score` | `numeric(5,2)` | NOT NULL | — | 0-100 weighted total, one decimal place in practice. |
| `confidence_level` | `numeric(5,2)` | NOT NULL | — | 0-100 data completeness, NOT statistical confidence. See ConfidenceBand. |
| `confidence_band` | `character varying(10)` | NOT NULL | — |  |
| `rank_position` | `integer` | NOT NULL | — | 1 = best. Unique within a run. |
| `breakdown` | `jsonb` | NOT NULL | — | CriterionScore[] driving the Score Ledger. Frozen at generation. |
| `rationale` | `text` | NOT NULL | — | Generated plain-English justification (FR-07). |
| `counterfactual` | `text` | NULL | — | The smallest single change that would lift this trainer to rank 1. NULL when no single change closes the gap — never invented. |
| `generated_at` | `timestamp with time zone` | NOT NULL | now() |  |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_predictions_confidence_band_valid` | b'c' | `CHECK (((confidence_band)::text = ANY ((ARRAY['LOW'::character varying, 'MODERATE'::character varying, 'HIGH'::character varying])::text[])))` |
| `ck_predictions_confidence_level_range` | b'c' | `CHECK (((confidence_level >= (0)::numeric) AND (confidence_level <= (100)::numeric)))` |
| `ck_predictions_prediction_score_range` | b'c' | `CHECK (((prediction_score >= (0)::numeric) AND (prediction_score <= (100)::numeric)))` |
| `ck_predictions_rank_position_positive` | b'c' | `CHECK ((rank_position > 0))` |
| `fk_predictions_programme_id_training_programmes` | b'f' | `FOREIGN KEY (programme_id) REFERENCES training_programmes(programme_id) ON DELETE CASCADE` |
| `fk_predictions_run_id_prediction_runs` | b'f' | `FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id) ON DELETE CASCADE` |
| `fk_predictions_trainer_id_trainers` | b'f' | `FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE RESTRICT` |
| `predictions_breakdown_not_null` | b'n' | `NOT NULL breakdown` |
| `predictions_confidence_band_not_null` | b'n' | `NOT NULL confidence_band` |
| `predictions_confidence_level_not_null` | b'n' | `NOT NULL confidence_level` |
| `predictions_generated_at_not_null` | b'n' | `NOT NULL generated_at` |
| `predictions_prediction_id_not_null` | b'n' | `NOT NULL prediction_id` |
| `predictions_prediction_score_not_null` | b'n' | `NOT NULL prediction_score` |
| `predictions_programme_id_not_null` | b'n' | `NOT NULL programme_id` |
| `predictions_rank_position_not_null` | b'n' | `NOT NULL rank_position` |
| `predictions_rationale_not_null` | b'n' | `NOT NULL rationale` |
| `predictions_run_id_not_null` | b'n' | `NOT NULL run_id` |
| `predictions_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `pk_predictions` | b'p' | `PRIMARY KEY (prediction_id)` |
| `uq_predictions_run_id_rank_position` | b'u' | `UNIQUE (run_id, rank_position)` |
| `uq_predictions_run_id_trainer_id` | b'u' | `UNIQUE (run_id, trainer_id)` |

**Indexes**

- `ix_predictions_programme_id` — `CREATE INDEX ix_predictions_programme_id ON public.predictions USING btree (programme_id)`
- `ix_predictions_run_rank` — `CREATE INDEX ix_predictions_run_rank ON public.predictions USING btree (run_id, rank_position)`
- `ix_predictions_trainer_id` — `CREATE INDEX ix_predictions_trainer_id ON public.predictions USING btree (trainer_id)`
- `pk_predictions` — `CREATE UNIQUE INDEX pk_predictions ON public.predictions USING btree (prediction_id)`
- `uq_predictions_run_id_rank_position` — `CREATE UNIQUE INDEX uq_predictions_run_id_rank_position ON public.predictions USING btree (run_id, rank_position)`
- `uq_predictions_run_id_trainer_id` — `CREATE UNIQUE INDEX uq_predictions_run_id_trainer_id ON public.predictions USING btree (run_id, trainer_id)`

---

## proficiency_levels

*Table.* Ordered proficiency levels with their scoring values (NFR-10).

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `level_id` | `bigint` | NOT NULL | identity |  |
| `code` | `character varying(20)` | NOT NULL | — |  |
| `name` | `character varying(40)` | NOT NULL | — |  |
| `rank_order` | `smallint` | NOT NULL | — | 1 = Basic, 4 = Expert. |
| `score_value` | `numeric(5,2)` | NOT NULL | — | 0-100 score fed to the SPECIALIZATION criterion. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_proficiency_levels_rank_order_positive` | b'c' | `CHECK ((rank_order > 0))` |
| `ck_proficiency_levels_score_value_range` | b'c' | `CHECK (((score_value >= (0)::numeric) AND (score_value <= (100)::numeric)))` |
| `proficiency_levels_code_not_null` | b'n' | `NOT NULL code` |
| `proficiency_levels_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `proficiency_levels_level_id_not_null` | b'n' | `NOT NULL level_id` |
| `proficiency_levels_name_not_null` | b'n' | `NOT NULL name` |
| `proficiency_levels_rank_order_not_null` | b'n' | `NOT NULL rank_order` |
| `proficiency_levels_score_value_not_null` | b'n' | `NOT NULL score_value` |
| `proficiency_levels_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_proficiency_levels` | b'p' | `PRIMARY KEY (level_id)` |
| `uq_proficiency_levels_code` | b'u' | `UNIQUE (code)` |
| `uq_proficiency_levels_rank_order` | b'u' | `UNIQUE (rank_order)` |

**Indexes**

- `pk_proficiency_levels` — `CREATE UNIQUE INDEX pk_proficiency_levels ON public.proficiency_levels USING btree (level_id)`
- `uq_proficiency_levels_code` — `CREATE UNIQUE INDEX uq_proficiency_levels_code ON public.proficiency_levels USING btree (code)`
- `uq_proficiency_levels_rank_order` — `CREATE UNIQUE INDEX uq_proficiency_levels_rank_order ON public.proficiency_levels USING btree (rank_order)`

---

## qualification_levels

*Table.* Ordered qualification levels with their scoring values (NFR-10).

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `level_id` | `bigint` | NOT NULL | identity |  |
| `code` | `character varying(24)` | NOT NULL | — | e.g. 'MASTERS'. Matches domain.ts. |
| `name` | `character varying(60)` | NOT NULL | — |  |
| `rank_order` | `smallint` | NOT NULL | — | 1 = Certificate, 6 = Doctorate. Compared by FR-05's minimum-qualification gate. |
| `score_value` | `numeric(5,2)` | NOT NULL | — | 0-100 score fed to the QUALIFICATION criterion. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_qualification_levels_rank_order_positive` | b'c' | `CHECK ((rank_order > 0))` |
| `ck_qualification_levels_score_value_range` | b'c' | `CHECK (((score_value >= (0)::numeric) AND (score_value <= (100)::numeric)))` |
| `qualification_levels_code_not_null` | b'n' | `NOT NULL code` |
| `qualification_levels_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `qualification_levels_level_id_not_null` | b'n' | `NOT NULL level_id` |
| `qualification_levels_name_not_null` | b'n' | `NOT NULL name` |
| `qualification_levels_rank_order_not_null` | b'n' | `NOT NULL rank_order` |
| `qualification_levels_score_value_not_null` | b'n' | `NOT NULL score_value` |
| `qualification_levels_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_qualification_levels` | b'p' | `PRIMARY KEY (level_id)` |
| `uq_qualification_levels_code` | b'u' | `UNIQUE (code)` |
| `uq_qualification_levels_rank_order` | b'u' | `UNIQUE (rank_order)` |

**Indexes**

- `pk_qualification_levels` — `CREATE UNIQUE INDEX pk_qualification_levels ON public.qualification_levels USING btree (level_id)`
- `uq_qualification_levels_code` — `CREATE UNIQUE INDEX uq_qualification_levels_code ON public.qualification_levels USING btree (code)`
- `uq_qualification_levels_rank_order` — `CREATE UNIQUE INDEX uq_qualification_levels_rank_order ON public.qualification_levels USING btree (rank_order)`

---

## refresh_tokens

*Table.* Hashed refresh tokens with rotation families for reuse detection.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `token_id` | `bigint` | NOT NULL | identity |  |
| `user_id` | `bigint` | NOT NULL | — | CASCADE: a deleted user's sessions are meaningless and must not outlive them. |
| `token_hash` | `character varying(255)` | NOT NULL | — | SHA-256 of the token. The token itself is never stored. |
| `family_id` | `uuid` | NOT NULL | — | Rotation family. Presenting a revoked token revokes every token sharing this id. |
| `expires_at` | `timestamp with time zone` | NOT NULL | — |  |
| `revoked_at` | `timestamp with time zone` | NULL | — | Revocation time. NULL means live — absence is the normal case. |
| `replaced_by_token_id` | `bigint` | NULL | — | The token issued when this one was rotated. Forms the rotation chain. |
| `created_by_ip` | `inet` | NULL | — |  |
| `user_agent` | `character varying(255)` | NULL | — |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `fk_refresh_tokens_replaced_by_token_id_refresh_tokens` | b'f' | `FOREIGN KEY (replaced_by_token_id) REFERENCES refresh_tokens(token_id) ON DELETE SET NULL` |
| `fk_refresh_tokens_user_id_users` | b'f' | `FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE` |
| `refresh_tokens_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `refresh_tokens_expires_at_not_null` | b'n' | `NOT NULL expires_at` |
| `refresh_tokens_family_id_not_null` | b'n' | `NOT NULL family_id` |
| `refresh_tokens_token_hash_not_null` | b'n' | `NOT NULL token_hash` |
| `refresh_tokens_token_id_not_null` | b'n' | `NOT NULL token_id` |
| `refresh_tokens_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `refresh_tokens_user_id_not_null` | b'n' | `NOT NULL user_id` |
| `pk_refresh_tokens` | b'p' | `PRIMARY KEY (token_id)` |

**Indexes**

- `ix_refresh_tokens_family_id` — `CREATE INDEX ix_refresh_tokens_family_id ON public.refresh_tokens USING btree (family_id)`
- `ix_refresh_tokens_replaced_by_token_id` — `CREATE INDEX ix_refresh_tokens_replaced_by_token_id ON public.refresh_tokens USING btree (replaced_by_token_id)`
- `ix_refresh_tokens_token_hash` — `CREATE INDEX ix_refresh_tokens_token_hash ON public.refresh_tokens USING btree (token_hash)`
- `ix_refresh_tokens_user_id` — `CREATE INDEX ix_refresh_tokens_user_id ON public.refresh_tokens USING btree (user_id)`
- `pk_refresh_tokens` — `CREATE UNIQUE INDEX pk_refresh_tokens ON public.refresh_tokens USING btree (token_id)`

---

## regions

*Table.* UPF policing regions.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `region_id` | `bigint` | NOT NULL | identity |  |
| `name` | `character varying(80)` | NOT NULL | — |  |
| `headquarters` | `character varying(80)` | NULL | — | Town hosting the regional headquarters. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `regions_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `regions_name_not_null` | b'n' | `NOT NULL name` |
| `regions_region_id_not_null` | b'n' | `NOT NULL region_id` |
| `regions_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_regions` | b'p' | `PRIMARY KEY (region_id)` |
| `uq_regions_name` | b'u' | `UNIQUE (name)` |

**Indexes**

- `pk_regions` — `CREATE UNIQUE INDEX pk_regions ON public.regions USING btree (region_id)`
- `uq_regions_name` — `CREATE UNIQUE INDEX uq_regions_name ON public.regions USING btree (name)`

---

## roles

*Table.* The four SRS actor roles. Seeded; not user-editable.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `role_id` | `bigint` | NOT NULL | identity |  |
| `name` | `character varying(40)` | NOT NULL | — | Machine name, e.g. TRAINING_ADMINISTRATOR. Matches domain.ts:RoleName. |
| `display_name` | `character varying(80)` | NOT NULL | — | Human-facing label, e.g. 'Training Administrator'. |
| `description` | `text` | NULL | — | What this role may do, in plain English. |
| `is_system` | `boolean` | NOT NULL | true | True for the four built-in roles, which must not be deleted. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_roles_name_valid` | b'c' | `CHECK (((name)::text = ANY ((ARRAY['TRAINING_ADMINISTRATOR'::character varying, 'TRAINING_OFFICER'::character varying, 'TRAINER'::character varying, 'SYSTEM_ADMINISTRATOR'::character varying])::text[])))` |
| `roles_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `roles_display_name_not_null` | b'n' | `NOT NULL display_name` |
| `roles_is_system_not_null` | b'n' | `NOT NULL is_system` |
| `roles_name_not_null` | b'n' | `NOT NULL name` |
| `roles_role_id_not_null` | b'n' | `NOT NULL role_id` |
| `roles_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_roles` | b'p' | `PRIMARY KEY (role_id)` |
| `uq_roles_name` | b'u' | `UNIQUE (name)` |

**Indexes**

- `pk_roles` — `CREATE UNIQUE INDEX pk_roles ON public.roles USING btree (role_id)`
- `uq_roles_name` — `CREATE UNIQUE INDEX uq_roles_name ON public.roles USING btree (name)`

---

## scoring_policies

*Table.* Versioned scoring weight sets. Exactly one is active (NFR-10).

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `policy_id` | `bigint` | NOT NULL | identity |  |
| `version` | `smallint` | NOT NULL | — | Monotonic policy version, from 1. |
| `name` | `character varying(80)` | NOT NULL | — |  |
| `is_active` | `boolean` | NOT NULL | false | Exactly one row may be true, enforced by a partial unique index. |
| `effective_from` | `timestamp with time zone` | NOT NULL | now() |  |
| `notes` | `text` | NULL | — | Why this policy was adopted. NULL for the initial policy. |
| `created_by_user_id` | `bigint` | NULL | — | NULL for the policy seeded at go-live, which no user created. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `fk_scoring_policies_created_by_user_id_users` | b'f' | `FOREIGN KEY (created_by_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `scoring_policies_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `scoring_policies_effective_from_not_null` | b'n' | `NOT NULL effective_from` |
| `scoring_policies_is_active_not_null` | b'n' | `NOT NULL is_active` |
| `scoring_policies_name_not_null` | b'n' | `NOT NULL name` |
| `scoring_policies_policy_id_not_null` | b'n' | `NOT NULL policy_id` |
| `scoring_policies_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `scoring_policies_version_not_null` | b'n' | `NOT NULL version` |
| `pk_scoring_policies` | b'p' | `PRIMARY KEY (policy_id)` |
| `uq_scoring_policies_version` | b'u' | `UNIQUE (version)` |

**Indexes**

- `ix_scoring_policies_created_by_user_id` — `CREATE INDEX ix_scoring_policies_created_by_user_id ON public.scoring_policies USING btree (created_by_user_id)`
- `pk_scoring_policies` — `CREATE UNIQUE INDEX pk_scoring_policies ON public.scoring_policies USING btree (policy_id)`
- `uq_scoring_policies_single_active` — `CREATE UNIQUE INDEX uq_scoring_policies_single_active ON public.scoring_policies USING btree (is_active) WHERE is_active`
- `uq_scoring_policies_version` — `CREATE UNIQUE INDEX uq_scoring_policies_version ON public.scoring_policies USING btree (version)`

---

## scoring_policy_weights

*Table.* Per-criterion weights. Rows not columns, so criteria change without migration.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `weight_id` | `bigint` | NOT NULL | identity |  |
| `policy_id` | `bigint` | NOT NULL | — | CASCADE: a weight has no meaning without its policy. |
| `criterion_key` | `character varying(32)` | NOT NULL | — | One of the five CriterionKey values. |
| `display_label` | `character varying(60)` | NOT NULL | — | e.g. 'Specialisation match'. |
| `weight` | `numeric(5,2)` | NOT NULL | — | Points available for this criterion. All five sum to 100. |
| `description` | `text` | NOT NULL | — | Plain-English explanation shown in the Weight Studio. |
| `sort_order` | `smallint` | NOT NULL | — | Display order, heaviest criterion first. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_scoring_policy_weights_criterion_key_valid` | b'c' | `CHECK (((criterion_key)::text = ANY ((ARRAY['SPECIALIZATION'::character varying, 'QUALIFICATION'::character varying, 'EXPERIENCE'::character varying, 'PERFORMANCE'::character varying, 'AVAILABILITY'::character varying])::text[])))` |
| `ck_scoring_policy_weights_weight_range` | b'c' | `CHECK (((weight >= (0)::numeric) AND (weight <= (100)::numeric)))` |
| `fk_scoring_policy_weights_policy_id_scoring_policies` | b'f' | `FOREIGN KEY (policy_id) REFERENCES scoring_policies(policy_id) ON DELETE CASCADE` |
| `scoring_policy_weights_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `scoring_policy_weights_criterion_key_not_null` | b'n' | `NOT NULL criterion_key` |
| `scoring_policy_weights_description_not_null` | b'n' | `NOT NULL description` |
| `scoring_policy_weights_display_label_not_null` | b'n' | `NOT NULL display_label` |
| `scoring_policy_weights_policy_id_not_null` | b'n' | `NOT NULL policy_id` |
| `scoring_policy_weights_sort_order_not_null` | b'n' | `NOT NULL sort_order` |
| `scoring_policy_weights_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `scoring_policy_weights_weight_id_not_null` | b'n' | `NOT NULL weight_id` |
| `scoring_policy_weights_weight_not_null` | b'n' | `NOT NULL weight` |
| `pk_scoring_policy_weights` | b'p' | `PRIMARY KEY (weight_id)` |
| `trg_scoring_policy_weights_sum` | b't' | `TRIGGER DEFERRABLE INITIALLY DEFERRED` |
| `uq_scoring_policy_weights_policy_criterion` | b'u' | `UNIQUE (policy_id, criterion_key)` |

**Indexes**

- `ix_scoring_policy_weights_policy_id` — `CREATE INDEX ix_scoring_policy_weights_policy_id ON public.scoring_policy_weights USING btree (policy_id)`
- `pk_scoring_policy_weights` — `CREATE UNIQUE INDEX pk_scoring_policy_weights ON public.scoring_policy_weights USING btree (weight_id)`
- `uq_scoring_policy_weights_policy_criterion` — `CREATE UNIQUE INDEX uq_scoring_policy_weights_policy_criterion ON public.scoring_policy_weights USING btree (policy_id, criterion_key)`

---

## specialization_areas

*Table.* Controlled vocabulary of training disciplines. BR-04 matches on this.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `specialization_area_id` | `bigint` | NOT NULL | identity |  |
| `name` | `character varying(120)` | NOT NULL | — |  |
| `description` | `text` | NULL | — |  |
| `directorate_id` | `bigint` | NULL | — | Directorate owning this discipline. NULL where ownership is shared. |
| `discipline_group` | `character varying(60)` | NULL | — | Subject grouping, e.g. 'Investigations'. Drives the SPECIALIZATION breadth bonus and the PERFORMANCE relevance test (ADR-0008). NULL means ungrouped, so neither rule fires — a safe default, not a silent failure. |
| `is_active` | `boolean` | NOT NULL | true |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `fk_specialization_areas_directorate_id_directorates` | b'f' | `FOREIGN KEY (directorate_id) REFERENCES directorates(directorate_id) ON DELETE RESTRICT` |
| `specialization_areas_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `specialization_areas_is_active_not_null` | b'n' | `NOT NULL is_active` |
| `specialization_areas_name_not_null` | b'n' | `NOT NULL name` |
| `specialization_areas_specialization_area_id_not_null` | b'n' | `NOT NULL specialization_area_id` |
| `specialization_areas_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_specialization_areas` | b'p' | `PRIMARY KEY (specialization_area_id)` |
| `uq_specialization_areas_name` | b'u' | `UNIQUE (name)` |

**Indexes**

- `ix_specialization_areas_directorate_id` — `CREATE INDEX ix_specialization_areas_directorate_id ON public.specialization_areas USING btree (directorate_id)`
- `ix_specialization_areas_discipline_group` — `CREATE INDEX ix_specialization_areas_discipline_group ON public.specialization_areas USING btree (discipline_group)`
- `pk_specialization_areas` — `CREATE UNIQUE INDEX pk_specialization_areas ON public.specialization_areas USING btree (specialization_area_id)`
- `uq_specialization_areas_name` — `CREATE UNIQUE INDEX uq_specialization_areas_name ON public.specialization_areas USING btree (name)`

---

## stations

*Table.* UPF establishments: stations, divisions, HQs, and training schools.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `station_id` | `bigint` | NOT NULL | identity |  |
| `name` | `character varying(120)` | NOT NULL | — |  |
| `region_id` | `bigint` | NOT NULL | — |  |
| `district` | `character varying(80)` | NULL | — | Administrative district. NULL for national HQ units. |
| `station_type` | `character varying(24)` | NOT NULL | — |  |
| `is_active` | `boolean` | NOT NULL | true |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_stations_station_type_valid` | b'c' | `CHECK (((station_type)::text = ANY ((ARRAY['HEADQUARTERS'::character varying, 'DIVISIONAL'::character varying, 'STATION'::character varying, 'POST'::character varying, 'TRAINING_INSTITUTION'::character varying, 'SPECIALISED_UNIT'::character varying])::text[])))` |
| `fk_stations_region_id_regions` | b'f' | `FOREIGN KEY (region_id) REFERENCES regions(region_id) ON DELETE RESTRICT` |
| `stations_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `stations_is_active_not_null` | b'n' | `NOT NULL is_active` |
| `stations_name_not_null` | b'n' | `NOT NULL name` |
| `stations_region_id_not_null` | b'n' | `NOT NULL region_id` |
| `stations_station_id_not_null` | b'n' | `NOT NULL station_id` |
| `stations_station_type_not_null` | b'n' | `NOT NULL station_type` |
| `stations_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_stations` | b'p' | `PRIMARY KEY (station_id)` |
| `uq_stations_name_region_id` | b'u' | `UNIQUE (name, region_id)` |

**Indexes**

- `ix_stations_region_id` — `CREATE INDEX ix_stations_region_id ON public.stations USING btree (region_id)`
- `ix_stations_station_type` — `CREATE INDEX ix_stations_station_type ON public.stations USING btree (station_type)`
- `pk_stations` — `CREATE UNIQUE INDEX pk_stations ON public.stations USING btree (station_id)`
- `uq_stations_name_region_id` — `CREATE UNIQUE INDEX uq_stations_name_region_id ON public.stations USING btree (name, region_id)`

---

## trainer_qualifications

*Table.* Qualifications held by a trainer. FR-03.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `qualification_id` | `bigint` | NOT NULL | identity |  |
| `trainer_id` | `bigint` | NOT NULL | — |  |
| `qualification_name` | `character varying(160)` | NOT NULL | — | e.g. 'MSc, Criminal Justice'. |
| `level_id` | `bigint` | NOT NULL | — |  |
| `institution_id` | `bigint` | NOT NULL | — |  |
| `year_obtained` | `smallint` | NOT NULL | — |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_trainer_qualifications_year_obtained_range` | b'c' | `CHECK (((year_obtained >= 1960) AND (year_obtained <= (EXTRACT(year FROM CURRENT_DATE))::smallint)))` |
| `fk_trainer_qualifications_institution_id_institutions` | b'f' | `FOREIGN KEY (institution_id) REFERENCES institutions(institution_id) ON DELETE RESTRICT` |
| `fk_trainer_qualifications_level_id_qualification_levels` | b'f' | `FOREIGN KEY (level_id) REFERENCES qualification_levels(level_id) ON DELETE RESTRICT` |
| `fk_trainer_qualifications_trainer_id_trainers` | b'f' | `FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE CASCADE` |
| `trainer_qualifications_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `trainer_qualifications_institution_id_not_null` | b'n' | `NOT NULL institution_id` |
| `trainer_qualifications_level_id_not_null` | b'n' | `NOT NULL level_id` |
| `trainer_qualifications_qualification_id_not_null` | b'n' | `NOT NULL qualification_id` |
| `trainer_qualifications_qualification_name_not_null` | b'n' | `NOT NULL qualification_name` |
| `trainer_qualifications_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `trainer_qualifications_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `trainer_qualifications_year_obtained_not_null` | b'n' | `NOT NULL year_obtained` |
| `pk_trainer_qualifications` | b'p' | `PRIMARY KEY (qualification_id)` |

**Indexes**

- `ix_trainer_qualifications_institution_id` — `CREATE INDEX ix_trainer_qualifications_institution_id ON public.trainer_qualifications USING btree (institution_id)`
- `ix_trainer_qualifications_level_id` — `CREATE INDEX ix_trainer_qualifications_level_id ON public.trainer_qualifications USING btree (level_id)`
- `ix_trainer_qualifications_trainer_id` — `CREATE INDEX ix_trainer_qualifications_trainer_id ON public.trainer_qualifications USING btree (trainer_id)`
- `pk_trainer_qualifications` — `CREATE UNIQUE INDEX pk_trainer_qualifications ON public.trainer_qualifications USING btree (qualification_id)`

---

## trainer_specializations

*Table.* Trainer proficiency per discipline. BR-04 matches on this.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `specialization_id` | `bigint` | NOT NULL | identity |  |
| `trainer_id` | `bigint` | NOT NULL | — |  |
| `specialization_area_id` | `bigint` | NOT NULL | — |  |
| `proficiency_level_id` | `bigint` | NOT NULL | — |  |
| `years_in_area` | `smallint` | NULL | — | Years worked in this discipline. NULL means not recorded. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_trainer_specializations_years_in_area_range` | b'c' | `CHECK (((years_in_area IS NULL) OR ((years_in_area >= 0) AND (years_in_area <= 50))))` |
| `fk_trainer_specializations_proficiency_level_id_profici_5923` | b'f' | `FOREIGN KEY (proficiency_level_id) REFERENCES proficiency_levels(level_id) ON DELETE RESTRICT` |
| `fk_trainer_specializations_specialization_area_id_speci_6619` | b'f' | `FOREIGN KEY (specialization_area_id) REFERENCES specialization_areas(specialization_area_id) ON DELETE RESTRICT` |
| `fk_trainer_specializations_trainer_id_trainers` | b'f' | `FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE CASCADE` |
| `trainer_specializations_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `trainer_specializations_proficiency_level_id_not_null` | b'n' | `NOT NULL proficiency_level_id` |
| `trainer_specializations_specialization_area_id_not_null` | b'n' | `NOT NULL specialization_area_id` |
| `trainer_specializations_specialization_id_not_null` | b'n' | `NOT NULL specialization_id` |
| `trainer_specializations_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `trainer_specializations_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_trainer_specializations` | b'p' | `PRIMARY KEY (specialization_id)` |
| `uq_trainer_specializations_trainer_area` | b'u' | `UNIQUE (trainer_id, specialization_area_id)` |

**Indexes**

- `ix_trainer_specializations_area_proficiency` — `CREATE INDEX ix_trainer_specializations_area_proficiency ON public.trainer_specializations USING btree (specialization_area_id, proficiency_level_id)`
- `ix_trainer_specializations_trainer_id` — `CREATE INDEX ix_trainer_specializations_trainer_id ON public.trainer_specializations USING btree (trainer_id)`
- `pk_trainer_specializations` — `CREATE UNIQUE INDEX pk_trainer_specializations ON public.trainer_specializations USING btree (specialization_id)`
- `uq_trainer_specializations_trainer_area` — `CREATE UNIQUE INDEX uq_trainer_specializations_trainer_area ON public.trainer_specializations USING btree (trainer_id, specialization_area_id)`

---

## trainer_unavailability

*Table.* Declared absence windows. Corroborates BR-03 exclusions and declines.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `unavailability_id` | `bigint` | NOT NULL | identity |  |
| `trainer_id` | `bigint` | NOT NULL | — |  |
| `start_date` | `date` | NOT NULL | — |  |
| `end_date` | `date` | NOT NULL | — | Inclusive last day of absence. |
| `reason` | `character varying(200)` | NOT NULL | — |  |
| `category` | `character varying(24)` | NOT NULL | — |  |
| `recorded_by_user_id` | `bigint` | NULL | — | Who recorded it. NULL when the trainer declared it themselves. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_trainer_unavailability_category_valid` | b'c' | `CHECK (((category)::text = ANY ((ARRAY['LEAVE'::character varying, 'COURT'::character varying, 'DEPLOYMENT'::character varying, 'STUDY'::character varying, 'MEDICAL'::character varying, 'OTHER'::character varying])::text[])))` |
| `ck_trainer_unavailability_end_date_after_start_date` | b'c' | `CHECK ((end_date >= start_date))` |
| `fk_trainer_unavailability_recorded_by_user_id_users` | b'f' | `FOREIGN KEY (recorded_by_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `fk_trainer_unavailability_trainer_id_trainers` | b'f' | `FOREIGN KEY (trainer_id) REFERENCES trainers(trainer_id) ON DELETE CASCADE` |
| `trainer_unavailability_category_not_null` | b'n' | `NOT NULL category` |
| `trainer_unavailability_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `trainer_unavailability_end_date_not_null` | b'n' | `NOT NULL end_date` |
| `trainer_unavailability_reason_not_null` | b'n' | `NOT NULL reason` |
| `trainer_unavailability_start_date_not_null` | b'n' | `NOT NULL start_date` |
| `trainer_unavailability_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `trainer_unavailability_unavailability_id_not_null` | b'n' | `NOT NULL unavailability_id` |
| `trainer_unavailability_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_trainer_unavailability` | b'p' | `PRIMARY KEY (unavailability_id)` |
| `ex_trainer_unavailability_no_overlap` | b'x' | `EXCLUDE USING gist (trainer_id WITH =, daterange(start_date, end_date, '[]'::text) WITH &&)` |

**Indexes**

- `ex_trainer_unavailability_no_overlap` — `CREATE INDEX ex_trainer_unavailability_no_overlap ON public.trainer_unavailability USING gist (trainer_id, daterange(start_date, end_date, '[]'::text))`
- `ix_trainer_unavailability_recorded_by_user_id` — `CREATE INDEX ix_trainer_unavailability_recorded_by_user_id ON public.trainer_unavailability USING btree (recorded_by_user_id)`
- `ix_trainer_unavailability_trainer_dates` — `CREATE INDEX ix_trainer_unavailability_trainer_dates ON public.trainer_unavailability USING btree (trainer_id, start_date, end_date)`
- `pk_trainer_unavailability` — `CREATE UNIQUE INDEX pk_trainer_unavailability ON public.trainer_unavailability USING btree (unavailability_id)`

---

## trainers

*Table.* Police officers available to deliver training. FR-03.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `trainer_id` | `bigint` | NOT NULL | identity |  |
| `user_id` | `bigint` | NOT NULL | — | The trainer's system account. One-to-one. |
| `force_number` | `character varying(20)` | NOT NULL | — | UPF force number, five digits, displayed as 'No. 41927'. The human identifier. |
| `rank_id` | `bigint` | NOT NULL | — |  |
| `station_id` | `bigint` | NOT NULL | — |  |
| `directorate_id` | `bigint` | NOT NULL | — |  |
| `date_of_enlistment` | `date` | NULL | — | Enlistment date. NULL where the record predates digitisation. |
| `years_experience` | `smallint` | NOT NULL | — | Years of service. Stored rather than derived from date_of_enlistment because that date is nullable for legacy records. The EXPERIENCE criterion saturates at 20 years (EXPERIENCE_CEILING_YEARS). |
| `availability_status` | `character varying(20)` | NOT NULL | 'AVAILABLE'::character varying | UNAVAILABLE is the BR-03 gate, applied before any scoring. |
| `contact_number` | `character varying(24)` | NOT NULL | — | Format '+256 772 419 273'. |
| `bio` | `text` | NULL | — | Free-text biography. NULL means not yet supplied. |
| `searchable_name` | `character varying(150)` | NOT NULL | — | Denormalised from users.full_name so the trigram index can be used. See class docstring. |
| `profile_completeness` | `smallint` | NOT NULL | '0'::smallint | 0-100. Contributes 35% of the confidence level shown beside every prediction. Derived from field presence (bio, contact, enlistment date, >=1 qualification, >=1 specialisation) and recomputed by Phase 2 on profile write. Stored, not computed on read, so a prediction's confidence can be reproduced exactly as it stood (conflict C6). |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_trainers_availability_status_valid` | b'c' | `CHECK (((availability_status)::text = ANY ((ARRAY['AVAILABLE'::character varying, 'ASSIGNED'::character varying, 'UNAVAILABLE'::character varying])::text[])))` |
| `ck_trainers_profile_completeness_range` | b'c' | `CHECK (((profile_completeness >= 0) AND (profile_completeness <= 100)))` |
| `ck_trainers_years_experience_range` | b'c' | `CHECK (((years_experience >= 0) AND (years_experience <= 50)))` |
| `fk_trainers_directorate_id_directorates` | b'f' | `FOREIGN KEY (directorate_id) REFERENCES directorates(directorate_id) ON DELETE RESTRICT` |
| `fk_trainers_rank_id_police_ranks` | b'f' | `FOREIGN KEY (rank_id) REFERENCES police_ranks(rank_id) ON DELETE RESTRICT` |
| `fk_trainers_station_id_stations` | b'f' | `FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE RESTRICT` |
| `fk_trainers_user_id_users` | b'f' | `FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `trainers_availability_status_not_null` | b'n' | `NOT NULL availability_status` |
| `trainers_contact_number_not_null` | b'n' | `NOT NULL contact_number` |
| `trainers_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `trainers_directorate_id_not_null` | b'n' | `NOT NULL directorate_id` |
| `trainers_force_number_not_null` | b'n' | `NOT NULL force_number` |
| `trainers_profile_completeness_not_null` | b'n' | `NOT NULL profile_completeness` |
| `trainers_rank_id_not_null` | b'n' | `NOT NULL rank_id` |
| `trainers_searchable_name_not_null` | b'n' | `NOT NULL searchable_name` |
| `trainers_station_id_not_null` | b'n' | `NOT NULL station_id` |
| `trainers_trainer_id_not_null` | b'n' | `NOT NULL trainer_id` |
| `trainers_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `trainers_user_id_not_null` | b'n' | `NOT NULL user_id` |
| `trainers_years_experience_not_null` | b'n' | `NOT NULL years_experience` |
| `pk_trainers` | b'p' | `PRIMARY KEY (trainer_id)` |
| `uq_trainers_force_number` | b'u' | `UNIQUE (force_number)` |
| `uq_trainers_user_id` | b'u' | `UNIQUE (user_id)` |

**Indexes**

- `ix_trainers_available` — `CREATE INDEX ix_trainers_available ON public.trainers USING btree (availability_status) WHERE ((availability_status)::text = 'AVAILABLE'::text)`
- `ix_trainers_directorate_id` — `CREATE INDEX ix_trainers_directorate_id ON public.trainers USING btree (directorate_id)`
- `ix_trainers_force_number_trgm` — `CREATE INDEX ix_trainers_force_number_trgm ON public.trainers USING gin (force_number gin_trgm_ops)`
- `ix_trainers_rank_id` — `CREATE INDEX ix_trainers_rank_id ON public.trainers USING btree (rank_id)`
- `ix_trainers_searchable_name_trgm` — `CREATE INDEX ix_trainers_searchable_name_trgm ON public.trainers USING gin (searchable_name gin_trgm_ops)`
- `ix_trainers_station_id` — `CREATE INDEX ix_trainers_station_id ON public.trainers USING btree (station_id)`
- `pk_trainers` — `CREATE UNIQUE INDEX pk_trainers ON public.trainers USING btree (trainer_id)`
- `uq_trainers_force_number` — `CREATE UNIQUE INDEX uq_trainers_force_number ON public.trainers USING btree (force_number)`
- `uq_trainers_user_id` — `CREATE UNIQUE INDEX uq_trainers_user_id ON public.trainers USING btree (user_id)`

---

## training_categories

*Table.* Delivery-mode taxonomy: Refresher, Induction, and so on.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `category_id` | `bigint` | NOT NULL | identity |  |
| `name` | `character varying(80)` | NOT NULL | — |  |
| `description` | `text` | NULL | — |  |
| `is_active` | `boolean` | NOT NULL | true |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `training_categories_category_id_not_null` | b'n' | `NOT NULL category_id` |
| `training_categories_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `training_categories_is_active_not_null` | b'n' | `NOT NULL is_active` |
| `training_categories_name_not_null` | b'n' | `NOT NULL name` |
| `training_categories_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_training_categories` | b'p' | `PRIMARY KEY (category_id)` |
| `uq_training_categories_name` | b'u' | `UNIQUE (name)` |

**Indexes**

- `pk_training_categories` — `CREATE UNIQUE INDEX pk_training_categories ON public.training_categories USING btree (category_id)`
- `uq_training_categories_name` — `CREATE UNIQUE INDEX uq_training_categories_name ON public.training_categories USING btree (name)`

---

## training_programmes

*Table.* Training courses and their requirements. FR-04, FR-05.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `programme_id` | `bigint` | NOT NULL | identity |  |
| `registry_number` | `character varying(32)` | NOT NULL | — | Human-facing identifier, e.g. 'TPS/REQ/2026/0132'. From next_registry_number('REQ'). |
| `title` | `character varying(200)` | NOT NULL | — |  |
| `category_id` | `bigint` | NOT NULL | — |  |
| `required_specialization_area_id` | `bigint` | NULL | — | NULL until FR-05 requirements are defined. See class docstring. |
| `minimum_experience` | `smallint` | NOT NULL | '0'::smallint | Minimum years of service. 0 means no bar. FR-05 gate. |
| `minimum_qualification_level_id` | `bigint` | NULL | — | Minimum qualification. NULL means none required — a meaningful absence. |
| `start_date` | `date` | NOT NULL | — |  |
| `end_date` | `date` | NOT NULL | — |  |
| `station_id` | `bigint` | NOT NULL | — | Venue where the course is delivered. |
| `expected_participants` | `smallint` | NULL | — | Planned intake size. NULL when not yet decided. |
| `status` | `character varying(24)` | NOT NULL | 'DRAFT'::character varying |  |
| `requirements_set_at` | `timestamp with time zone` | NULL | — | When FR-05 requirements were defined. NULL while still DRAFT. |
| `requirements_changed_since_prediction` | `boolean` | NOT NULL | false | Drives the FR-05 re-rank banner: the ranking on screen may be stale. |
| `created_by_user_id` | `bigint` | NOT NULL | — |  |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_training_programmes_end_date_after_start_date` | b'c' | `CHECK ((end_date >= start_date))` |
| `ck_training_programmes_expected_participants_positive` | b'c' | `CHECK (((expected_participants IS NULL) OR (expected_participants > 0)))` |
| `ck_training_programmes_minimum_experience_range` | b'c' | `CHECK (((minimum_experience >= 0) AND (minimum_experience <= 50)))` |
| `ck_training_programmes_requirements_set_beyond_draft` | b'c' | `CHECK ((((status)::text = 'DRAFT'::text) OR ((status)::text = 'CANCELLED'::text) OR (required_specialization_area_id IS NOT NULL)))` |
| `ck_training_programmes_status_valid` | b'c' | `CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'REQUIREMENTS_SET'::character varying, 'PREDICTED'::character varying, 'AWAITING_RESPONSE'::character varying, 'ALLOCATED'::character varying, 'CONDUCTED'::character varying, 'EVALUATED'::character varying, 'CANCELLED'::character varying])::text[])))` |
| `fk_training_programmes_category_id_training_categories` | b'f' | `FOREIGN KEY (category_id) REFERENCES training_categories(category_id) ON DELETE RESTRICT` |
| `fk_training_programmes_created_by_user_id_users` | b'f' | `FOREIGN KEY (created_by_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `fk_training_programmes_minimum_qualification_level_id_q_8bb4` | b'f' | `FOREIGN KEY (minimum_qualification_level_id) REFERENCES qualification_levels(level_id) ON DELETE RESTRICT` |
| `fk_training_programmes_required_specialization_area_id__6db4` | b'f' | `FOREIGN KEY (required_specialization_area_id) REFERENCES specialization_areas(specialization_area_id) ON DELETE RESTRICT` |
| `fk_training_programmes_station_id_stations` | b'f' | `FOREIGN KEY (station_id) REFERENCES stations(station_id) ON DELETE RESTRICT` |
| `training_programmes_category_id_not_null` | b'n' | `NOT NULL category_id` |
| `training_programmes_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `training_programmes_created_by_user_id_not_null` | b'n' | `NOT NULL created_by_user_id` |
| `training_programmes_end_date_not_null` | b'n' | `NOT NULL end_date` |
| `training_programmes_minimum_experience_not_null` | b'n' | `NOT NULL minimum_experience` |
| `training_programmes_programme_id_not_null` | b'n' | `NOT NULL programme_id` |
| `training_programmes_registry_number_not_null` | b'n' | `NOT NULL registry_number` |
| `training_programmes_requirements_changed_since_predict_not_null` | b'n' | `NOT NULL requirements_changed_since_prediction` |
| `training_programmes_start_date_not_null` | b'n' | `NOT NULL start_date` |
| `training_programmes_station_id_not_null` | b'n' | `NOT NULL station_id` |
| `training_programmes_status_not_null` | b'n' | `NOT NULL status` |
| `training_programmes_title_not_null` | b'n' | `NOT NULL title` |
| `training_programmes_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `pk_training_programmes` | b'p' | `PRIMARY KEY (programme_id)` |
| `uq_training_programmes_registry_number` | b'u' | `UNIQUE (registry_number)` |

**Indexes**

- `ix_training_programmes_category_id` — `CREATE INDEX ix_training_programmes_category_id ON public.training_programmes USING btree (category_id)`
- `ix_training_programmes_created_by_user_id` — `CREATE INDEX ix_training_programmes_created_by_user_id ON public.training_programmes USING btree (created_by_user_id)`
- `ix_training_programmes_dates` — `CREATE INDEX ix_training_programmes_dates ON public.training_programmes USING btree (start_date, end_date)`
- `ix_training_programmes_minimum_qualification_level_id` — `CREATE INDEX ix_training_programmes_minimum_qualification_level_id ON public.training_programmes USING btree (minimum_qualification_level_id)`
- `ix_training_programmes_required_specialization_area_id` — `CREATE INDEX ix_training_programmes_required_specialization_area_id ON public.training_programmes USING btree (required_specialization_area_id)`
- `ix_training_programmes_station_id` — `CREATE INDEX ix_training_programmes_station_id ON public.training_programmes USING btree (station_id)`
- `ix_training_programmes_status` — `CREATE INDEX ix_training_programmes_status ON public.training_programmes USING btree (status)`
- `ix_training_programmes_title_trgm` — `CREATE INDEX ix_training_programmes_title_trgm ON public.training_programmes USING gin (title gin_trgm_ops)`
- `pk_training_programmes` — `CREATE UNIQUE INDEX pk_training_programmes ON public.training_programmes USING btree (programme_id)`
- `uq_training_programmes_registry_number` — `CREATE UNIQUE INDEX uq_training_programmes_registry_number ON public.training_programmes USING btree (registry_number)`

---

## users

*Table.* System user accounts. FR-01 authentication, FR-02 authorisation.

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `user_id` | `bigint` | NOT NULL | identity |  |
| `username` | `citext` | NOT NULL | — | Case-insensitive login name. |
| `email` | `citext` | NOT NULL | — | Case-insensitive email address. |
| `password_hash` | `character varying(255)` | NOT NULL | — | Argon2id hash. Never logged, never returned by any endpoint. |
| `full_name` | `character varying(150)` | NOT NULL | — |  |
| `role_id` | `bigint` | NOT NULL | — |  |
| `rank_id` | `bigint` | NULL | — | Police rank. NULL for any future civilian or service account. |
| `account_status` | `character varying(20)` | NOT NULL | 'ACTIVE'::character varying |  |
| `failed_login_count` | `smallint` | NOT NULL | '0'::smallint | Consecutive failed sign-ins. Reset to 0 on success (FR-01). |
| `locked_until` | `timestamp with time zone` | NULL | — | Lockout expiry. NULL means not locked — the normal state (FR-01). |
| `last_login_at` | `timestamp with time zone` | NULL | — | Last successful sign-in. NULL means the account has never been used. |
| `must_change_password` | `boolean` | NOT NULL | false | True after an administrator resets the password. |
| `created_by_user_id` | `bigint` | NULL | — | Administrator who created this account. NULL for the bootstrap administrator. |
| `created_at` | `timestamp with time zone` | NOT NULL | now() | Row creation time (UTC). |
| `updated_at` | `timestamp with time zone` | NOT NULL | now() | Last modification time (UTC), maintained by the set_updated_at trigger. |

**Constraints**

| Name | Kind | Definition |
|---|---|---|
| `ck_users_account_status_valid` | b'c' | `CHECK (((account_status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'SUSPENDED'::character varying, 'DEACTIVATED'::character varying])::text[])))` |
| `ck_users_failed_login_count_non_negative` | b'c' | `CHECK ((failed_login_count >= 0))` |
| `fk_users_created_by_user_id_users` | b'f' | `FOREIGN KEY (created_by_user_id) REFERENCES users(user_id) ON DELETE RESTRICT` |
| `fk_users_rank_id_police_ranks` | b'f' | `FOREIGN KEY (rank_id) REFERENCES police_ranks(rank_id) ON DELETE RESTRICT` |
| `fk_users_role_id_roles` | b'f' | `FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE RESTRICT` |
| `users_account_status_not_null` | b'n' | `NOT NULL account_status` |
| `users_created_at_not_null` | b'n' | `NOT NULL created_at` |
| `users_email_not_null` | b'n' | `NOT NULL email` |
| `users_failed_login_count_not_null` | b'n' | `NOT NULL failed_login_count` |
| `users_full_name_not_null` | b'n' | `NOT NULL full_name` |
| `users_must_change_password_not_null` | b'n' | `NOT NULL must_change_password` |
| `users_password_hash_not_null` | b'n' | `NOT NULL password_hash` |
| `users_role_id_not_null` | b'n' | `NOT NULL role_id` |
| `users_updated_at_not_null` | b'n' | `NOT NULL updated_at` |
| `users_user_id_not_null` | b'n' | `NOT NULL user_id` |
| `users_username_not_null` | b'n' | `NOT NULL username` |
| `pk_users` | b'p' | `PRIMARY KEY (user_id)` |
| `uq_users_email` | b'u' | `UNIQUE (email)` |
| `uq_users_username` | b'u' | `UNIQUE (username)` |

**Indexes**

- `ix_users_account_status` — `CREATE INDEX ix_users_account_status ON public.users USING btree (account_status)`
- `ix_users_created_by_user_id` — `CREATE INDEX ix_users_created_by_user_id ON public.users USING btree (created_by_user_id)`
- `ix_users_rank_id` — `CREATE INDEX ix_users_rank_id ON public.users USING btree (rank_id)`
- `ix_users_role_id` — `CREATE INDEX ix_users_role_id ON public.users USING btree (role_id)`
- `pk_users` — `CREATE UNIQUE INDEX pk_users ON public.users USING btree (user_id)`
- `uq_users_email` — `CREATE UNIQUE INDEX uq_users_email ON public.users USING btree (email)`
- `uq_users_username` — `CREATE UNIQUE INDEX uq_users_username ON public.users USING btree (username)`

---

## v_trainer_scoring_facts

*View.* Per-trainer scoring facts: evaluation depth, mean rating, per-discipline breakdown, current workload, and profile depth. A plain view, so a just-recorded evaluation influences the very next prediction (ADR-0007).

| Column | Type | Null | Default | Description |
|---|---|---|---|---|
| `trainer_id` | `bigint` | NULL | — |  |
| `evaluation_count` | `bigint` | NULL | — |  |
| `mean_score_awarded` | `numeric` | NULL | — |  |
| `last_evaluation_date` | `date` | NULL | — |  |
| `evaluations_by_discipline_group` | `jsonb` | NULL | — |  |
| `mean_by_discipline_group` | `jsonb` | NULL | — |  |
| `active_allocation_count` | `bigint` | NULL | — |  |
| `last_assignment_date` | `timestamp with time zone` | NULL | — |  |
| `total_allocation_count` | `bigint` | NULL | — |  |
| `qualification_count` | `bigint` | NULL | — |  |
| `specialization_count` | `bigint` | NULL | — |  |
| `profile_completeness` | `smallint` | NULL | — |  |

---

## Functions

| Function | Description |
|---|---|
| `check_policy_weights_sum()` | Deferred check that a policy's criterion weights total 100. Fires at COMMIT. |
| `next_registry_number(family text)` | Returns TPS/{FAMILY}/{YYYY}/{NNNN}. Families: REQ, ALL, EVL. Concurrency-safe. |
| `prevent_audit_mutation()` | Raises on UPDATE or DELETE against audit_logs. Enforces FR-13 below the application. |
| `set_updated_at()` | Sets updated_at to now() on every UPDATE. Applied to all tables carrying the column. |

## Triggers

The shared `set_updated_at` triggers are omitted — one exists on every table carrying `updated_at`, and listing 23 identical rows would only obscure the two that matter.

| Table | Trigger | Definition |
|---|---|---|
| `audit_logs` | `trg_audit_logs_immutable` | `CREATE TRIGGER trg_audit_logs_immutable BEFORE DELETE OR UPDATE ON public.audit_logs FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation()` |
| `scoring_policy_weights` | `trg_scoring_policy_weights_sum` | `CREATE CONSTRAINT TRIGGER trg_scoring_policy_weights_sum AFTER INSERT OR DELETE OR UPDATE ON public.scoring_policy_weights DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_policy_weights_sum()` |

## Sequences

Registry sequences back `next_registry_number()` (§5.9). **Gaps are expected**: a sequence does not roll back with its transaction. A registry number is an identifier, not a count, so a gap carries no meaning and must not be repaired — renumbering would change identifiers on documents that have already been issued.

| Sequence | Last value |
|---|---|
| `registry_all_seq` | 55 |
| `registry_evl_seq` | 46 |
| `registry_req_seq` | 46 |

