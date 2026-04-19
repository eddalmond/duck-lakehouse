import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def mesh_dirs(tmp_dir):
    dirs = {
        "inbox": tmp_dir / "inbox",
        "processing": tmp_dir / "processing",
        "archive": tmp_dir / "archive",
        "logs": tmp_dir / "logs",
        "error": tmp_dir / "error",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


@pytest.fixture
def ducklake_dirs(tmp_dir):
    catalog = tmp_dir / "catalog"
    data = tmp_dir / "parquet"
    catalog.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)
    return {
        "catalog_path": str(catalog / "vaccination_lake.ducklake"),
        "data_path": str(data),
        "base_dir": tmp_dir,
    }


@pytest.fixture(autouse=True)
def isolate_env():
    original = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original)


@pytest.fixture
def sample_csv_content():
    header = '"NHS_NUMBER"|"PERSON_FORENAME"|"PERSON_SURNAME"|"PERSON_DOB"|"PERSON_GENDER_CODE"|"PERSON_POSTCODE"|"DATE_AND_TIME"|"SITE_CODE"|"SITE_CODE_TYPE_URI"|"UNIQUE_ID"|"UNIQUE_ID_URI"|"ACTION_FLAG"|"PERFORMING_PROFESSIONAL_FORENAME"|"PERFORMING_PROFESSIONAL_SURNAME"|"RECORDED_DATE"|"PRIMARY_SOURCE"|"VACCINATION_PROCEDURE_CODE"|"VACCINATION_PROCEDURE_TERM"|"DOSE_SEQUENCE"|"VACCINE_PRODUCT_CODE"|"VACCINE_PRODUCT_TERM"|"VACCINE_MANUFACTURER"|"BATCH_NUMBER"|"EXPIRY_DATE"|"SITE_OF_VACCINATION_CODE"|"SITE_OF_VACCINATION_TERM"|"ROUTE_OF_VACCINATION_CODE"|"ROUTE_OF_VACCINATION_TERM"|"DOSE_AMOUNT"|"DOSE_UNIT_CODE"|"DOSE_UNIT_TERM"|"INDICATION_CODE"|"LOCATION_CODE"|"LOCATION_CODE_TYPE_URI"'
    row1 = '"9990000001"|"Oliver"|"Smith"|"19850315"|"1"|"SW1A 1AA"|"20260101T10000000"|"B0C4P"|"https://fhir.nhs.uk/Id/ods-organization-code"|"uuid-001"|"https://supplier/B0C4P/identifiers/vacc"|"new"|"Jane"|"Doe"|"20260101"|"TRUE"|"822851000000102"|"Seasonal influenza vaccination"|"1"|"22704311000001104"|"Fluenz Tetra"|"AstraZeneca"|"ABCD1234"|"20270101"|"368208006"|"Left upper arm"|"78421000"|"Intramuscular route"|"0.2"|"258773002"|"Millilitre"|"161096004"|"B0C4P"|"https://fhir.nhs.uk/Id/ods-organization-code"'
    row2 = '"9990000002"|"Amelia"|"Brown"|"19900822"|"2"|"M1 1AE"|"20260102T11000000"|"RX8"|"https://fhir.nhs.uk/Id/ods-organization-code"|"uuid-002"|"https://supplier/RX8/identifiers/vacc"|"new"|"Mark"|"Jones"|"20260102"|"TRUE"|"1324681000000101"|"COVID-19 first dose"|"1"|"39114911000001105"|"Comirnaty"|"Pfizer-BioNTech"|"EFGH5678"|"20270102"|"368209003"|"Right upper arm"|"78421000"|"Intramuscular route"|"0.3"|"258773002"|"Millilitre"|"443684005"|"RX8"|"https://fhir.nhs.uk/Id/ods-organization-code"'
    return header + "\r\n" + row1 + "\r\n" + row2 + "\r\n"


@pytest.fixture
def sample_csv_file(mesh_dirs, sample_csv_content):
    filepath = mesh_dirs["archive"] / "Flu_Vaccinations_v5_TEST_20260101.csv"
    filepath.write_text(sample_csv_content, encoding="utf-8")
    return filepath


@pytest.fixture
def app_with_temp_dirs(ducklake_dirs, mesh_dirs):
    from dashboard.app import app as flask_app

    flask_app.config["TESTING"] = True

    with flask_app.app_context():
        with patch.multiple(
            "dashboard.app",
            CATALOG_PATH=Path(ducklake_dirs["catalog_path"]),
            DATA_PATH=Path(ducklake_dirs["data_path"]),
            CATALOG_DIR=Path(ducklake_dirs["catalog_path"]).parent,
            DATA_DIR=Path(ducklake_dirs["data_path"]),
            ARCHIVE_DIR=mesh_dirs["archive"],
            INBOX_DIR=mesh_dirs["inbox"],
            PROCESSING_DIR=mesh_dirs["processing"],
            LOGS_DIR=mesh_dirs["logs"],
        ):
            yield flask_app


@pytest.fixture
def client(app_with_temp_dirs):
    return app_with_temp_dirs.test_client()
