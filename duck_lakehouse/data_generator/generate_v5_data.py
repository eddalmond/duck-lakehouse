#!/usr/bin/env python3
"""
NHS Vaccination v5.1 Data Generator

Generates realistic pipe-delimited CSV files compliant with the NHSE Daily
Vaccination Events (In-Bound) Extract Technical Specification v5.1.

Each field is double-quoted and delimited by pipe characters.
Filenames follow: {DiseaseType}_Vaccinations_v5_{OrgCode}_{Timestamp}.csv
"""

import csv
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

V5_FIELDS = [
    "NHS_NUMBER",
    "PERSON_FORENAME",
    "PERSON_SURNAME",
    "PERSON_DOB",
    "PERSON_GENDER_CODE",
    "PERSON_POSTCODE",
    "DATE_AND_TIME",
    "SITE_CODE",
    "SITE_CODE_TYPE_URI",
    "UNIQUE_ID",
    "UNIQUE_ID_URI",
    "ACTION_FLAG",
    "PERFORMING_PROFESSIONAL_FORENAME",
    "PERFORMING_PROFESSIONAL_SURNAME",
    "RECORDED_DATE",
    "PRIMARY_SOURCE",
    "VACCINATION_PROCEDURE_CODE",
    "VACCINATION_PROCEDURE_TERM",
    "DOSE_SEQUENCE",
    "VACCINE_PRODUCT_CODE",
    "VACCINE_PRODUCT_TERM",
    "VACCINE_MANUFACTURER",
    "BATCH_NUMBER",
    "EXPIRY_DATE",
    "SITE_OF_VACCINATION_CODE",
    "SITE_OF_VACCINATION_TERM",
    "ROUTE_OF_VACCINATION_CODE",
    "ROUTE_OF_VACCINATION_TERM",
    "DOSE_AMOUNT",
    "DOSE_UNIT_CODE",
    "DOSE_UNIT_TERM",
    "INDICATION_CODE",
    "LOCATION_CODE",
    "LOCATION_CODE_TYPE_URI",
]

FORENAMES = [
    "Oliver", "George", "Amelia", "Isla", "Noah", "Arthur",
    "Mia", "Ella", "Leo", "Grace", "Harry", "Sophia",
    "Charlie", "Emily", "Jack", "Lily", "William", "Ava",
    "Henry", "Ivy",
]

SURNAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Taylor",
    "Davies", "Evans", "Wilson", "Thomas", "Roberts", "Walker",
    "Wright", "Thompson", "White", "Edwards", "Hughes", "Green",
    "Clark", "Patel",
]

POSTCODES = [
    "SW1A 1AA", "M1 1AE", "B1 1AA", "LS1 4AP", "NE1 1AA",
    "L1 1AA", "CF1 1AA", "EH1 1AA", "BS1 1AA", "EC1A 1BB",
    "W1A 0AX", "SE1 7PB", "G1 1AA", "BT1 1AA", "DD1 1AA",
]

SITE_CODES = ["B0C4P", "RX8", "F8G09", "Y0228", "E84080"]

VACCINE_TYPES = {
    "Flu": {
        "procedures": [
            ("822851000000102", "Seasonal influenza vaccination given (situation)"),
        ],
        "products": [
            ("22704311000001104", "Fluenz Tetra nasal suspension (AstraZeneca UK Ltd)", "AstraZeneca", "0.2"),
            ("35727511000001100", "Influvac sub-unit Tetra vaccine suspension for injection (BGP Products Ltd)", "BGP Products", "0.5"),
        ],
        "routes": [("78421000", "Intramuscular route"), ("46713006", "Nasal route")],
        "indication_code": "161096004",
    },
    "COVID": {
        "procedures": [
            ("1324681000000101", "Administration of first dose of severe acute respiratory syndrome coronavirus 2 vaccine"),
            ("1324691000000104", "Administration of second dose of severe acute respiratory syndrome coronavirus 2 vaccine"),
            ("1362591000000103", "Administration of booster dose of severe acute respiratory syndrome coronavirus 2 vaccine"),
        ],
        "products": [
            ("39114911000001105", "COVID-19 Vaccine Comirnaty 30micrograms/0.3ml dose concentrate for dispersion for injection multidose vials (Pfizer-BioNTech)", "Pfizer-BioNTech", "0.3"),
            ("39115011000001105", "COVID-19 Vaccine Vaxzevria suspension for injection multidose vials (AstraZeneca)", "AstraZeneca", "0.5"),
        ],
        "routes": [("78421000", "Intramuscular route")],
        "indication_code": "443684005",
    },
    "RSV": {
        "procedures": [
            ("1324701000000103", "Respiratory syncytial virus vaccination"),
        ],
        "products": [
            ("4601781000001109", "Abrysvo suspension for injection 0.5ml pre-filled syringes (Pfizer Ltd)", "Pfizer", "0.5"),
        ],
        "routes": [("78421000", "Intramuscular route")],
        "indication_code": "55607004",
    },
    "HPV": {
        "procedures": [
            ("308081000000105", "Measles mumps and rubella vaccination - first dose (procedure)"),
        ],
        "products": [
            ("34986411000001101", "Gardasil 9 suspension for injection 0.5ml pre-filled syringes (Merck Sharp & Dohme (UK) Ltd)", "MSD", "0.5"),
        ],
        "routes": [("78421000", "Intramuscular route")],
        "indication_code": "363408001",
    },
    "MMR": {
        "procedures": [
            ("308081000000105", "Measles mumps and rubella vaccination - first dose (procedure)"),
            ("170433008", "Administration of second dose of vaccine product containing only Measles morbillivirus and Mumps orthorubulavirus and Rubella virus antigens (procedure)"),
        ],
        "products": [
            ("10384511000001108", "MMRvaxPRO powder and solvent for suspension for injection 0.5ml vials (Merck Sharp & Dohme (UK) Ltd)", "MSD", "0.5"),
        ],
        "routes": [("78421000", "Intramuscular route"), ("445298008", "Subcutaneous route")],
        "indication_code": "363408001",
    },
}

BODY_SITES = [
    ("368208006", "Left upper arm structure"),
    ("368209003", "Right upper arm structure"),
    ("78333006", "Structure of left thigh"),
    ("11207009", "Structure of right thigh"),
]

GENDER_CODES = ["0", "1", "2", "9"]
ACTION_FLAGS = ["new", "update", "delete"]


def _nhs_number_checksum(d9: str) -> str:
    digits = [int(d) for d in d9]
    weights = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(d * w for d, w in zip(digits, weights))
    remainder = 11 - (total % 11)
    if remainder == 11:
        check = 0
    elif remainder == 10:
        return None
    else:
        check = remainder
    return d9 + str(check)


def generate_nhs_number() -> str:
    while True:
        d9 = "".join(str(random.randint(0, 9)) for _ in range(9))
        if d9[0] != "0":
            result = _nhs_number_checksum(d9)
            if result:
                return result


def _format_datetime(dt: datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%S00")


def generate_record(
    vaccine_type: str,
    dose_sequence: int = 1,
    action_flag: str = "new",
    vacc_date: datetime = None,
) -> dict:
    if vacc_date is None:
        vacc_date = datetime.now() - timedelta(days=random.randint(1, 90))

    vtype = VACCINE_TYPES[vaccine_type]
    proc_idx = min(dose_sequence - 1, len(vtype["procedures"]) - 1)
    proc_code, proc_term = vtype["procedures"][proc_idx]
    product = random.choice(vtype["products"])
    route = random.choice(vtype["routes"])
    body_site = random.choice(BODY_SITES)

    nhs_number = generate_nhs_number()
    forename = random.choice(FORENAMES)
    surname = random.choice(SURNAMES)
    dob_year = random.randint(1940, 2020)
    dob_month = random.randint(1, 12)
    dob_day = random.randint(1, 28)
    dob = f"{dob_year:04d}{dob_month:02d}{dob_day:02d}"
    gender = random.choice(["1", "2"])
    postcode = random.choice(POSTCODES)
    site_code = random.choice(SITE_CODES)
    unique_id = str(uuid.uuid4())
    batch_number = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
    expiry = (vacc_date + timedelta(days=365)).strftime("%Y%m%d")
    recorded = vacc_date.strftime("%Y%m%d")

    return {
        "NHS_NUMBER": nhs_number,
        "PERSON_FORENAME": forename,
        "PERSON_SURNAME": surname,
        "PERSON_DOB": dob,
        "PERSON_GENDER_CODE": gender,
        "PERSON_POSTCODE": postcode,
        "DATE_AND_TIME": _format_datetime(vacc_date),
        "SITE_CODE": site_code,
        "SITE_CODE_TYPE_URI": "https://fhir.nhs.uk/Id/ods-organization-code",
        "UNIQUE_ID": unique_id,
        "UNIQUE_ID_URI": f"https://supplierABC/{site_code}/identifiers/vacc",
        "ACTION_FLAG": action_flag,
        "PERFORMING_PROFESSIONAL_FORENAME": random.choice(FORENAMES),
        "PERFORMING_PROFESSIONAL_SURNAME": random.choice(SURNAMES),
        "RECORDED_DATE": recorded,
        "PRIMARY_SOURCE": "TRUE",
        "VACCINATION_PROCEDURE_CODE": proc_code,
        "VACCINATION_PROCEDURE_TERM": proc_term,
        "DOSE_SEQUENCE": str(dose_sequence),
        "VACCINE_PRODUCT_CODE": product[0],
        "VACCINE_PRODUCT_TERM": product[1],
        "VACCINE_MANUFACTURER": product[2],
        "BATCH_NUMBER": batch_number,
        "EXPIRY_DATE": expiry,
        "SITE_OF_VACCINATION_CODE": body_site[0],
        "SITE_OF_VACCINATION_TERM": body_site[1],
        "ROUTE_OF_VACCINATION_CODE": route[0],
        "ROUTE_OF_VACCINATION_TERM": route[1],
        "DOSE_AMOUNT": product[3],
        "DOSE_UNIT_CODE": "258773002",
        "DOSE_UNIT_TERM": "Millilitre",
        "INDICATION_CODE": vtype["indication_code"],
        "LOCATION_CODE": site_code,
        "LOCATION_CODE_TYPE_URI": "https://fhir.nhs.uk/Id/ods-organization-code",
    }


def generate_filename(vaccine_type: str, org_code: str = "ABC123") -> str:
    now = datetime.now()
    ts = now.strftime("%Y%m%dT%H%M%S00")
    return f"{vaccine_type}_Vaccinations_v5_{org_code}_{ts}.csv"


def write_v5_csv(
    records: List[dict],
    output_dir: Path,
    vaccine_type: str,
    org_code: str = "ABC123",
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = generate_filename(vaccine_type, org_code)
    filepath = output_dir / filename

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        header = "|".join(f'"{field}"' for field in V5_FIELDS)
        f.write(header + "\r\n")

        for record in records:
            row = []
            for field in V5_FIELDS:
                value = record.get(field, "")
                escaped = str(value).replace('"', '\\"')
                row.append(f'"{escaped}"')
            f.write("|".join(row) + "\r\n")

    return filepath


def generate_dataset(
    vaccine_type: str,
    num_records: int = 100,
    output_dir: str = "output",
    org_code: str = "ABC123",
) -> Path:
    records = []
    for i in range(num_records):
        dose = random.choices([1, 2, 3], weights=[0.5, 0.3, 0.2])[0]
        action = random.choices(
            ACTION_FLAGS, weights=[0.85, 0.10, 0.05]
        )[0]
        vacc_date = datetime.now() - timedelta(days=random.randint(1, 90))
        records.append(generate_record(vaccine_type, dose, action, vacc_date))

    return write_v5_csv(records, Path(output_dir), vaccine_type, org_code)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate NHS v5 vaccination CSVs")
    parser.add_argument(
        "--type",
        choices=list(VACCINE_TYPES.keys()) + ["all"],
        default="all",
        help="Vaccine type to generate (default: all)",
    )
    parser.add_argument(
        "--records", type=int, default=200, help="Records per vaccine type"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory (default: package/mesh_simulator/inbox)",
    )
    parser.add_argument("--org-code", default="ABC123", help="Sending org code")
    args = parser.parse_args()

    if args.output is None:
        pkg_dir = Path(__file__).resolve().parent.parent
        args.output = str(pkg_dir / "mesh_simulator" / "inbox")

    types = list(VACCINE_TYPES.keys()) if args.type == "all" else [args.type]

    for vtype in types:
        path = generate_dataset(vtype, args.records, args.output, args.org_code)
        print(f"Generated {args.records} {vtype} records -> {path}")


if __name__ == "__main__":
    main()