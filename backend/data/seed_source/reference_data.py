"""Static UPF reference data (§5.1).

Plain literal tables, kept apart from the generator so the two concerns stay
separable: this file is *what the Uganda Police Force is*, and ``generator.py`` is
*what happened in it*. Correcting a rank or adding a station touches only this file.

Per ADR-0009 these are the **real** UPF lists, not the simplified ones in
``frontend/src/lib/constants.ts``. The frontend types every one of these values as a
plain ``string``, so nothing in the TypeScript contract breaks; only rendered labels
differ, and ``constants.ts`` is updated in Phase 3.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, NamedTuple

from app.models.enums import (
    CriterionKey,
    InstitutionType,
    ManagementLevel,
    RoleName,
    StationType,
)


class RankSeed(NamedTuple):
    """A rung on the UPF rank ladder."""

    order: int
    code: str
    full_name: str
    level: str
    appointments: str


#: The UPF rank ladder, junior to senior, with the appointments the force actually
#: attaches to each rank. ``appointments`` is what keeps seeded people plausible:
#: §7.2 forbids giving a four-year officer the rank of SSP.
POLICE_RANKS: Final[tuple[RankSeed, ...]] = (
    RankSeed(1, "SPC", "Special Police Constable", ManagementLevel.JUNIOR, "Beat patrol"),
    RankSeed(
        2,
        "PC",
        "Police Constable",
        ManagementLevel.JUNIOR,
        "Communications, station diary, cells guard, armoury, patrol",
    ),
    RankSeed(3, "CPL", "Corporal", ManagementLevel.JUNIOR, "First level supervisor"),
    RankSeed(
        4,
        "SGT",
        "Sergeant",
        ManagementLevel.JUNIOR,
        "Head of station discipline, second level supervisor",
    ),
    RankSeed(
        5, "AIP", "Assistant Inspector of Police", ManagementLevel.JUNIOR, "Third level supervisor"
    ),
    RankSeed(
        6,
        "IP",
        "Inspector of Police",
        ManagementLevel.JUNIOR,
        "In charge of a police post, supervision",
    ),
    RankSeed(
        7,
        "ASP",
        "Assistant Superintendent of Police",
        ManagementLevel.MIDDLE,
        "Head of station, head of section at district, District Human Resource Officer",
    ),
    RankSeed(
        8,
        "SP",
        "Superintendent of Police",
        ManagementLevel.MIDDLE,
        "Head of divisional police station, head of district crime investigation, staff officer",
    ),
    RankSeed(
        9,
        "SSP",
        "Senior Superintendent of Police",
        ManagementLevel.MIDDLE,
        "Head of section, District Police Commander, staff officer",
    ),
    RankSeed(
        10,
        "ACP",
        "Assistant Commissioner of Police",
        ManagementLevel.SENIOR,
        "Assistant head of department, Regional Police Commander",
    ),
    RankSeed(
        11,
        "CP",
        "Commissioner of Police",
        ManagementLevel.SENIOR,
        "Head of department, head of specialised unit",
    ),
    RankSeed(
        12,
        "SCP",
        "Senior Commissioner of Police",
        ManagementLevel.SENIOR,
        "Deputy head of directorate",
    ),
    RankSeed(
        13,
        "AIGP",
        "Assistant Inspector General of Police",
        ManagementLevel.STRATEGIC,
        "Head of directorate",
    ),
    RankSeed(
        14,
        "DIGP",
        "Deputy Inspector General of Police",
        ManagementLevel.STRATEGIC,
        "Deputy head of institution",
    ),
    RankSeed(
        15, "IGP", "Inspector General of Police", ManagementLevel.STRATEGIC, "Head of institution"
    ),
)

#: Ranks the frontend's ``PoliceRank`` union knows about (``domain.ts:18``). Every
#: seeded person is constrained to this subset, so no seeded row can violate the
#: TypeScript contract even though the ladder above is complete (conflict C8).
FRONTEND_KNOWN_RANKS: Final[frozenset[str]] = frozenset(
    {"PC", "CPL", "SGT", "AIP", "IP", "ASP", "SP", "SSP", "ACP"}
)


class RoleSeed(NamedTuple):
    """One of the four SRS actors."""

    name: str
    display_name: str
    description: str


ROLES: Final[tuple[RoleSeed, ...]] = (
    RoleSeed(
        RoleName.TRAINING_ADMINISTRATOR,
        "Training Administrator",
        "Approves allocations and tunes weighting policy.",
    ),
    RoleSeed(
        RoleName.TRAINING_OFFICER,
        "Training Officer",
        "Raises training requests and defines requirements.",
    ),
    RoleSeed(RoleName.TRAINER, "Trainer", "Delivers training; accepts or declines assignments."),
    RoleSeed(
        RoleName.SYSTEM_ADMINISTRATOR,
        "System Administrator",
        "Manages users, roles, and system health.",
    ),
)


class DirectorateSeed(NamedTuple):
    """A UPF directorate."""

    name: str
    abbreviation: str | None
    is_training_authority: bool


#: The 17 UPF directorates. Human Resource Development owns training and is the
#: organisational home of TPS.
DIRECTORATES: Final[tuple[DirectorateSeed, ...]] = (
    DirectorateSeed("Crime Intelligence", "CI", False),
    DirectorateSeed("Chief Political Commissariat", "CPC", False),
    DirectorateSeed("Counter Terrorism", "CT", False),
    DirectorateSeed("Criminal Investigations", "CID", False),
    DirectorateSeed("Forensic Services", "DFS", False),
    DirectorateSeed("Human Resource Administration & Management", "HRAM", False),
    DirectorateSeed("Human Resource Development", "HRD", True),
    DirectorateSeed("Human Rights and Legal Services", "HRLS", False),
    DirectorateSeed("Information & Communication Technology", "ICT", False),
    DirectorateSeed("Interpol & International Relations", "IIR", False),
    DirectorateSeed("Logistics and Engineering", "L&E", False),
    DirectorateSeed("Operations", "OPS", False),
    DirectorateSeed("Police Fire Prevention and Rescue Services", "PFPRS", False),
    DirectorateSeed("Police Health Services", "PHS", False),
    DirectorateSeed("Research, Planning & Development", "RPD", False),
    DirectorateSeed("Traffic and Road Safety", "TRS", False),
    DirectorateSeed("Welfare and Production", "W&P", False),
)


class RegionSeed(NamedTuple):
    """A UPF policing region and its headquarters town."""

    name: str
    headquarters: str


#: The 29 real UPF policing regions.
REGIONS: Final[tuple[RegionSeed, ...]] = (
    RegionSeed("KMP East", "Jinja Road"),
    RegionSeed("KMP North", "Wandegeya"),
    RegionSeed("KMP South", "Katwe"),
    RegionSeed("Albertine North", "Hoima"),
    RegionSeed("Albertine South", "Kikuube"),
    RegionSeed("Budongo", "Masindi"),
    RegionSeed("Aswa East", "Kitgum"),
    RegionSeed("Aswa West", "Gulu"),
    RegionSeed("Bukedi North", "Tororo"),
    RegionSeed("Bukedi South", "Busia"),
    RegionSeed("Busoga East", "Jinja"),
    RegionSeed("Busoga North", "Kamuli"),
    RegionSeed("East Kyoga", "Soroti"),
    RegionSeed("South Kyoga", "Kumi"),
    RegionSeed("Elgon", "Mbale"),
    RegionSeed("Greater Bushenyi", "Bushenyi"),
    RegionSeed("Katonga", "Mpigi"),
    RegionSeed("Kidepo", "Kaabong"),
    RegionSeed("Kigezi", "Kabale"),
    RegionSeed("Rwizi", "Mbarara"),
    RegionSeed("Savannah", "Nakasongola"),
    RegionSeed("Sezibwa", "Mukono"),
    RegionSeed("North Kyoga", "Lira"),
    RegionSeed("Rwenzori East", "Fort Portal"),
    RegionSeed("Rwenzori West", "Kasese"),
    RegionSeed("West Nile", "Arua"),
    RegionSeed("Greater Masaka", "Masaka"),
    RegionSeed("Wamala", "Mityana"),
    RegionSeed("Mount Moroto", "Moroto"),
)


class StationSeed(NamedTuple):
    """A UPF establishment."""

    name: str
    region: str
    district: str
    station_type: str


#: Stations, divisions, headquarters, and the eight training institutions.
STATIONS: Final[tuple[StationSeed, ...]] = (
    StationSeed("Police Headquarters Naguru", "KMP East", "Kampala", StationType.HEADQUARTERS),
    StationSeed("Central Police Station Kampala", "KMP East", "Kampala", StationType.DIVISIONAL),
    StationSeed("Old Kampala", "KMP South", "Kampala", StationType.DIVISIONAL),
    StationSeed("Kira Road", "KMP East", "Kampala", StationType.DIVISIONAL),
    StationSeed("Jinja Road", "KMP East", "Kampala", StationType.DIVISIONAL),
    StationSeed("Katwe", "KMP South", "Kampala", StationType.DIVISIONAL),
    StationSeed("Kabalagala", "KMP South", "Kampala", StationType.STATION),
    StationSeed("Nsambya", "KMP South", "Kampala", StationType.STATION),
    StationSeed("Kibuli", "KMP South", "Kampala", StationType.SPECIALISED_UNIT),
    StationSeed("Wandegeya", "KMP North", "Kampala", StationType.DIVISIONAL),
    StationSeed("Ntinda", "KMP North", "Kampala", StationType.STATION),
    StationSeed("Kawempe", "KMP North", "Kampala", StationType.DIVISIONAL),
    StationSeed("Nateete", "KMP South", "Kampala", StationType.STATION),
    StationSeed("Entebbe", "Katonga", "Wakiso", StationType.DIVISIONAL),
    StationSeed("Mukono", "Sezibwa", "Mukono", StationType.DIVISIONAL),
    StationSeed("Jinja Central", "Busoga East", "Jinja", StationType.DIVISIONAL),
    StationSeed("Mbale", "Elgon", "Mbale", StationType.DIVISIONAL),
    StationSeed("Mbarara", "Rwizi", "Mbarara", StationType.DIVISIONAL),
    StationSeed("Gulu", "Aswa West", "Gulu", StationType.DIVISIONAL),
    StationSeed("Arua", "West Nile", "Arua", StationType.DIVISIONAL),
    StationSeed("Lira", "North Kyoga", "Lira", StationType.DIVISIONAL),
    StationSeed("Fort Portal", "Rwenzori East", "Kabarole", StationType.DIVISIONAL),
    StationSeed("Masaka", "Greater Masaka", "Masaka", StationType.DIVISIONAL),
    StationSeed("Soroti", "East Kyoga", "Soroti", StationType.DIVISIONAL),
    StationSeed("Hoima", "Albertine North", "Hoima", StationType.DIVISIONAL),
    StationSeed("Moroto", "Mount Moroto", "Moroto", StationType.DIVISIONAL),
    StationSeed("Kabale", "Kigezi", "Kabale", StationType.DIVISIONAL),
    StationSeed("Tororo", "Bukedi North", "Tororo", StationType.DIVISIONAL),
    StationSeed("Masindi", "Budongo", "Masindi", StationType.DIVISIONAL),
    StationSeed("Kasese", "Rwenzori West", "Kasese", StationType.DIVISIONAL),
    StationSeed("Mityana", "Wamala", "Mityana", StationType.DIVISIONAL),
    # Training institutions — course venues.
    StationSeed(
        "Police Senior Command and Staff College, Bwebajja",
        "Katonga",
        "Wakiso",
        StationType.TRAINING_INSTITUTION,
    ),
    StationSeed(
        "Police Training School, Kabalye", "Budongo", "Masindi", StationType.TRAINING_INSTITUTION
    ),
    StationSeed(
        "Police Training School, Ikafe", "West Nile", "Yumbe", StationType.TRAINING_INSTITUTION
    ),
    StationSeed(
        "Anti-Terrorism Training School, Olilim",
        "East Kyoga",
        "Katakwi",
        StationType.TRAINING_INSTITUTION,
    ),
    StationSeed(
        "Canine Training School, Nsambya", "KMP South", "Kampala", StationType.TRAINING_INSTITUTION
    ),
    StationSeed(
        "Marine Training School, Kajjansi", "Katonga", "Wakiso", StationType.TRAINING_INSTITUTION
    ),
    StationSeed(
        "Fire and Rescue Training School, Nsambya",
        "KMP South",
        "Kampala",
        StationType.TRAINING_INSTITUTION,
    ),
    StationSeed(
        "Field Force Unit Training School, Kabalye",
        "Budongo",
        "Masindi",
        StationType.TRAINING_INSTITUTION,
    ),
)

TRAINING_INSTITUTION_STATIONS: Final[tuple[str, ...]] = tuple(
    station.name for station in STATIONS if station.station_type == StationType.TRAINING_INSTITUTION
)


class SpecializationSeed(NamedTuple):
    """A training discipline.

    ``discipline_group`` is the subject grouping the scoring engine needs (ADR-0008);
    ``directorate`` is the UPF directorate that owns the discipline.
    """

    name: str
    discipline_group: str
    directorate: str
    description: str


#: The 24 disciplines BR-04 matches against. ``discipline_group`` values are taken
#: verbatim from the frontend's ``SPECIALIZATION_CATEGORY`` map, because the scoring
#: engine's breadth bonus and performance relevance test compare them.
SPECIALIZATION_AREAS: Final[tuple[SpecializationSeed, ...]] = (
    SpecializationSeed(
        "Cybercrime Investigation",
        "Investigations",
        "Criminal Investigations",
        "Investigation of offences committed through computer systems and networks.",
    ),
    SpecializationSeed(
        "Digital Forensics",
        "Forensics",
        "Forensic Services",
        "Recovery and analysis of evidence from digital devices.",
    ),
    SpecializationSeed(
        "Criminal Investigation",
        "Investigations",
        "Criminal Investigations",
        "General criminal investigation practice and case management.",
    ),
    SpecializationSeed(
        "Scene of Crime Management",
        "Forensics",
        "Forensic Services",
        "Securing, documenting, and processing a crime scene.",
    ),
    SpecializationSeed(
        "Fingerprint and Ballistics",
        "Forensics",
        "Forensic Services",
        "Comparison of friction ridge and firearm evidence.",
    ),
    SpecializationSeed(
        "Community Policing",
        "Community Policing",
        "Operations",
        "Partnership policing with communities and local councils.",
    ),
    SpecializationSeed(
        "Public Order Management",
        "Public Order",
        "Operations",
        "Lawful management of assemblies and demonstrations.",
    ),
    SpecializationSeed(
        "Traffic Management and Road Safety",
        "Traffic",
        "Traffic and Road Safety",
        "Road traffic enforcement, crash investigation, and safety education.",
    ),
    SpecializationSeed(
        "Counter-Terrorism",
        "Counter-Terrorism",
        "Counter Terrorism",
        "Prevention, detection, and response to terrorist activity.",
    ),
    SpecializationSeed(
        "Firearms and Tactical Training",
        "Firearms",
        "Operations",
        "Safe handling, marksmanship, and tactical employment of firearms.",
    ),
    SpecializationSeed(
        "Canine Handling", "Firearms", "Operations", "Deployment and care of police service dogs."
    ),
    SpecializationSeed(
        "Marine Operations", "Marine", "Operations", "Waterborne patrol, search, and rescue."
    ),
    SpecializationSeed(
        "Human Rights and Professional Standards",
        "Professional Standards",
        "Human Rights and Legal Services",
        "Human rights compliance and professional conduct.",
    ),
    SpecializationSeed(
        "Anti-Corruption",
        "Professional Standards",
        "Human Rights and Legal Services",
        "Detection and investigation of corruption offences.",
    ),
    SpecializationSeed(
        "Child and Family Protection",
        "Child Protection",
        "Criminal Investigations",
        "Investigation and support in offences against children and families.",
    ),
    SpecializationSeed(
        "Gender-Based Violence Response",
        "Child Protection",
        "Criminal Investigations",
        "Response to and investigation of gender-based violence.",
    ),
    SpecializationSeed(
        "Drill and Ceremonial",
        "Public Order",
        "Operations",
        "Foot drill, parade command, and ceremonial duties.",
    ),
    SpecializationSeed(
        "First Aid and Emergency Response",
        "Community Policing",
        "Police Health Services",
        "Pre-hospital emergency care and incident first response.",
    ),
    SpecializationSeed(
        "Intelligence Analysis",
        "Intelligence",
        "Crime Intelligence",
        "Collection, collation, and analysis of criminal intelligence.",
    ),
    SpecializationSeed(
        "Border Management",
        "Counter-Terrorism",
        "Interpol & International Relations",
        "Border control, immigration liaison, and cross-border crime.",
    ),
    SpecializationSeed(
        "Crowd Control",
        "Public Order",
        "Operations",
        "Crowd dynamics and proportionate use of force.",
    ),
    SpecializationSeed(
        "Fire and Rescue Operations",
        "Marine",
        "Police Fire Prevention and Rescue Services",
        "Firefighting, extrication, and technical rescue.",
    ),
    SpecializationSeed(
        "Records and Registry Management",
        "Records Management",
        "Research, Planning & Development",
        "Custody, indexing, and disposal of police records.",
    ),
    SpecializationSeed(
        "ICT Systems Administration",
        "Records Management",
        "Information & Communication Technology",
        "Administration of police information systems and networks.",
    ),
)


class CategorySeed(NamedTuple):
    """A training delivery category."""

    name: str
    description: str


#: Delivery-mode taxonomy per §5.1. Distinct from ``discipline_group``, which is
#: subject — see ADR-0008.
TRAINING_CATEGORIES: Final[tuple[CategorySeed, ...]] = (
    CategorySeed(
        "Initial Training", "Recruit and foundation training for newly enlisted officers."
    ),
    CategorySeed("Refresher", "Periodic refresher of previously acquired skills."),
    CategorySeed("Specialised Skills", "Technical training in a specific discipline."),
    CategorySeed("Command and Leadership", "Command, staff, and leadership development."),
    CategorySeed("Induction", "Orientation on posting to a new unit or role."),
    CategorySeed("Pre-Deployment", "Preparation for a specific operation or deployment."),
    CategorySeed(
        "Regional/International", "Courses delivered with regional or international partners."
    ),
    CategorySeed(
        "Instructor Development", "Training of trainers: instructional technique and assessment."
    ),
)


class InstitutionSeed(NamedTuple):
    """A qualification-awarding institution."""

    name: str
    institution_type: str
    country: str


#: ``POLICE`` institutions earn the QUALIFICATION criterion's +8 bonus. That is a
#: column here, not a hard-coded name list as in the frontend, so a newly added
#: police school qualifies automatically.
INSTITUTIONS: Final[tuple[InstitutionSeed, ...]] = (
    InstitutionSeed(
        "Police Senior Command and Staff College Bwebajja", InstitutionType.POLICE, "Uganda"
    ),
    InstitutionSeed("Police Training School Kabalye", InstitutionType.POLICE, "Uganda"),
    InstitutionSeed("Police Training School Ikafe", InstitutionType.POLICE, "Uganda"),
    InstitutionSeed("Anti-Terrorism Training School Olilim", InstitutionType.POLICE, "Uganda"),
    InstitutionSeed("Canine Training School Nsambya", InstitutionType.POLICE, "Uganda"),
    InstitutionSeed("Marine Training School Kajjansi", InstitutionType.POLICE, "Uganda"),
    InstitutionSeed("Makerere University", InstitutionType.UNIVERSITY, "Uganda"),
    InstitutionSeed("Kyambogo University", InstitutionType.UNIVERSITY, "Uganda"),
    InstitutionSeed("Uganda Christian University Mukono", InstitutionType.UNIVERSITY, "Uganda"),
    InstitutionSeed("Nkumba University", InstitutionType.UNIVERSITY, "Uganda"),
    InstitutionSeed("Uganda Management Institute", InstitutionType.UNIVERSITY, "Uganda"),
    InstitutionSeed(
        "Mbarara University of Science and Technology", InstitutionType.UNIVERSITY, "Uganda"
    ),
    InstitutionSeed("Busitema University", InstitutionType.UNIVERSITY, "Uganda"),
    InstitutionSeed("Gulu University", InstitutionType.UNIVERSITY, "Uganda"),
    InstitutionSeed("Law Development Centre", InstitutionType.PROFESSIONAL, "Uganda"),
    InstitutionSeed(
        "Uganda Institute of Information and Communications Technology",
        InstitutionType.PROFESSIONAL,
        "Uganda",
    ),
    InstitutionSeed("EAPCCO Regional Training Centre", InstitutionType.INTERNATIONAL, "Kenya"),
    InstitutionSeed(
        "INTERPOL Global Complex for Innovation", InstitutionType.INTERNATIONAL, "Singapore"
    ),
    InstitutionSeed(
        "Ethiopian Police University College", InstitutionType.INTERNATIONAL, "Ethiopia"
    ),
    InstitutionSeed(
        "Kenya National Police College Kiganjo", InstitutionType.INTERNATIONAL, "Kenya"
    ),
)


class LevelSeed(NamedTuple):
    """An ordered level with the score the algorithm assigns it."""

    order: int
    code: str
    name: str
    score: Decimal


QUALIFICATION_LEVELS: Final[tuple[LevelSeed, ...]] = (
    LevelSeed(1, "CERTIFICATE", "Certificate", Decimal("35.00")),
    LevelSeed(2, "DIPLOMA", "Diploma", Decimal("50.00")),
    LevelSeed(3, "BACHELORS", "Bachelor's Degree", Decimal("65.00")),
    LevelSeed(4, "POSTGRAD_DIPLOMA", "Postgraduate Diploma", Decimal("78.00")),
    LevelSeed(5, "MASTERS", "Master's Degree", Decimal("90.00")),
    LevelSeed(6, "DOCTORATE", "Doctorate", Decimal("100.00")),
)

PROFICIENCY_LEVELS: Final[tuple[LevelSeed, ...]] = (
    LevelSeed(1, "BASIC", "Basic", Decimal("40.00")),
    LevelSeed(2, "INTERMEDIATE", "Intermediate", Decimal("65.00")),
    LevelSeed(3, "ADVANCED", "Advanced", Decimal("85.00")),
    LevelSeed(4, "EXPERT", "Expert", Decimal("100.00")),
)


class WeightSeed(NamedTuple):
    """A criterion's weight under the standard policy."""

    key: str
    label: str
    weight: Decimal
    sort_order: int
    description: str


#: Policy version 1, "Standard policy". Weights sum to 100, enforced at commit by the
#: deferred constraint trigger installed in migration 0002.
STANDARD_POLICY_WEIGHTS: Final[tuple[WeightSeed, ...]] = (
    WeightSeed(
        CriterionKey.SPECIALIZATION,
        "Specialisation match",
        Decimal("30.00"),
        1,
        "How closely the trainer's proven area of expertise matches what this course requires.",
    ),
    WeightSeed(
        CriterionKey.PERFORMANCE,
        "Proven performance",
        Decimal("25.00"),
        2,
        "The trainer's average rating from courses they have delivered before.",
    ),
    WeightSeed(
        CriterionKey.EXPERIENCE,
        "Years of service",
        Decimal("20.00"),
        3,
        "Length of service, counted up to a twenty-year ceiling.",
    ),
    WeightSeed(
        CriterionKey.QUALIFICATION,
        "Qualification",
        Decimal("15.00"),
        4,
        "The trainer's highest formal academic or professional qualification.",
    ),
    WeightSeed(
        CriterionKey.AVAILABILITY,
        "Availability",
        Decimal("10.00"),
        5,
        "How much spare teaching capacity the trainer has right now.",
    ),
)

# --- People (§7.2) ---------------------------------------------------------

#: Given names split by gender so the roster reads roughly 30% women.
FEMALE_GIVEN_NAMES: Final[tuple[str, ...]] = (
    "Grace",
    "Sarah",
    "Aisha",
    "Betty",
    "Immaculate",
    "Robinah",
    "Prossy",
    "Zainab",
    "Harriet",
    "Norah",
    "Specioza",
    "Justine",
    "Florence",
    "Agnes",
    "Rehema",
    "Winnie",
    "Christine",
    "Jalia",
    "Peace",
    "Sylvia",
)

MALE_GIVEN_NAMES: Final[tuple[str, ...]] = (
    "Joseph",
    "Moses",
    "Hassan",
    "Ronald",
    "Patrick",
    "Godfrey",
    "Fredrick",
    "Ibrahim",
    "Denis",
    "Wilson",
    "Julius",
    "Emmanuel",
    "Samuel",
    "Charles",
    "Richard",
    "Abdul",
    "Peter",
    "Vincent",
    "Bosco",
    "Alex",
)

#: Surnames drawn from across Uganda's language groups: Baganda, Basoga, Banyankole,
#: Bakiga, Acholi, Langi, Iteso, Bagisu, Lugbara, Batoro, Alur, Karimojong.
SURNAMES: Final[tuple[str, ...]] = (
    "Okello",
    "Nabirye",
    "Mugisha",
    "Kyaligonza",
    "Ssentongo",
    "Wanyama",
    "Draru",
    "Byaruhanga",
    "Opio",
    "Namubiru",
    "Otim",
    "Businge",
    "Achieng",
    "Kizza",
    "Adiru",
    "Tumwine",
    "Masaba",
    "Candia",
    "Lubega",
    "Amuge",
    "Ojok",
    "Nakato",
    "Wekesa",
    "Atuhaire",
    "Andama",
    "Nalwoga",
    "Ekwaru",
    "Kabagambe",
    "Odongo",
    "Ainembabazi",
    "Akullo",
    "Twinomugisha",
    "Nangobi",
    "Ochieng",
    "Kemigisha",
    "Muhwezi",
    "Aturinda",
    "Wasswa",
)

#: Real Ugandan mobile prefixes (§7.2).
PHONE_PREFIXES: Final[tuple[str, ...]] = (
    "0772",
    "0782",
    "0752",
    "0700",
    "0701",
    "0703",
    "0784",
    "0759",
    "0787",
)

#: Rank bands that are plausible for years of service (§7.2). Used to keep rank and
#: seniority consistent — a four-year officer is never an SSP.
RANK_YEARS_BAND: Final[dict[str, tuple[int, int]]] = {
    "AIP": (3, 8),
    "IP": (6, 14),
    "ASP": (10, 20),
    "SP": (15, 26),
    "SSP": (18, 30),
    "ACP": (22, 35),
}

#: Ranks a trainer may hold, weighted toward the inspectorate and junior gazetted
#: officers, who are the UPF's actual instructor population (§7.2).
TRAINER_RANK_WEIGHTS: Final[tuple[tuple[str, int], ...]] = (
    ("AIP", 16),
    ("IP", 34),
    ("ASP", 28),
    ("SP", 15),
    ("SSP", 7),
)

QUALIFICATION_NAMES: Final[dict[str, str]] = {
    "DOCTORATE": "PhD, Security Studies",
    "MASTERS": "MSc, Criminal Justice",
    "POSTGRAD_DIPLOMA": "PG Diploma, Public Administration",
    "BACHELORS": "BA, Social Sciences",
    "DIPLOMA": "Diploma, Police Studies",
    "CERTIFICATE": "Certificate, Basic Policing",
}

EVALUATOR_COMMENTS: Final[tuple[str, ...]] = (
    "Clear delivery; strong command of the subject.",
    "Well prepared; engaged the trainees throughout.",
    "Good practical exercises; time-keeping could improve.",
    "Excellent case studies drawn from real investigations.",
    "Solid session; handled questions confidently.",
    "Thorough coverage of the syllabus; good use of scenarios.",
    "Confident instructor; trainees rated the session highly.",
)
