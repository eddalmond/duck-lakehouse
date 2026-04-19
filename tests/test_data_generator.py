import re

from duck_lakehouse.data_generator.generate_v5_data import (
    V5_FIELDS,
    ACTION_FLAGS,
    FORENAMES,
    SURNAMES,
    VACCINE_TYPES,
    generate_dataset,
    generate_filename,
    generate_nhs_number,
    generate_record,
    write_v5_csv,
)
from duck_lakehouse.data_generator.v5_fields import (
    V5_FIELDS as V5_FIELDS_SPEC,
    MANDATORY_FIELDS,
    REQUIRED_FIELDS,
)


class TestNhsNumberGeneration:
    def test_generates_valid_nhs_number(self):
        nhs = generate_nhs_number()
        assert len(nhs) == 10
        assert nhs.isdigit()

    def test_nhs_starts_with_9(self):
        for _ in range(20):
            nhs = generate_nhs_number()
            assert nhs[0] == "9"

    def test_nhs_checksum_valid(self):
        for _ in range(20):
            nhs = generate_nhs_number()
            d9 = [int(d) for d in nhs[:9]]
            weights = [10, 9, 8, 7, 6, 5, 4, 3, 2]
            total = sum(d * w for d, w in zip(d9, weights))
            remainder = 11 - (total % 11)
            expected_check = 0 if remainder == 11 else remainder
            assert int(nhs[9]) == expected_check

    def test_generates_unique_numbers(self):
        numbers = {generate_nhs_number() for _ in range(100)}
        assert len(numbers) > 90


class TestRecordGeneration:
    def test_generate_flu_record(self):
        rec = generate_record("Flu")
        assert rec["NHS_NUMBER"]
        assert rec["PERSON_FORENAME"] in FORENAMES
        assert rec["PERSON_SURNAME"] in SURNAMES
        assert rec["VACCINE_PRODUCT_CODE"]
        assert rec["ACTION_FLAG"] in ACTION_FLAGS

    def test_generate_covid_record(self):
        rec = generate_record("COVID")
        assert rec["VACCINE_PRODUCT_CODE"]
        assert rec["VACCINE_MANUFACTURER"]

    def test_generate_with_dose_sequence(self):
        rec = generate_record("Flu", dose_sequence=2)
        assert rec["DOSE_SEQUENCE"] == "2"

    def test_generate_with_action_flag(self):
        rec = generate_record("Flu", action_flag="update")
        assert rec["ACTION_FLAG"] == "update"

    def test_record_has_all_v5_fields(self):
        rec = generate_record("Flu")
        for field in V5_FIELDS:
            assert field in rec, f"Missing field: {field}"

    def test_record_mandatory_fields_not_empty(self):
        rec = generate_record("COVID")
        for field in MANDATORY_FIELDS:
            assert rec[field], f"Mandatory field {field} is empty"


class TestFilename:
    def test_filename_format(self):
        name = generate_filename("Flu", "TEST001")
        pattern = r"Flu_Vaccinations_v5_TEST001_\d{8}T\d{6}\d{2}"
        assert re.match(pattern, name), f"Filename {name} doesn't match pattern"

    def test_filename_with_default_org(self):
        name = generate_filename("COVID")
        assert name.startswith("COVID_Vaccinations_v5_ABC123_")


class TestCsvWrite:
    def test_write_creates_file(self, tmp_dir):
        records = [generate_record("Flu") for _ in range(5)]
        path = write_v5_csv(records, tmp_dir, "Flu")
        assert path.exists()
        assert path.suffix == ".csv"

    def test_write_csv_has_header(self, tmp_dir):
        records = [generate_record("Flu")]
        path = write_v5_csv(records, tmp_dir, "Flu")
        content = path.read_text(encoding="utf-8")
        first_line = content.split("\r\n")[0]
        for field in V5_FIELDS:
            assert f'"{field}"' in first_line

    def test_write_csv_pipe_delimited(self, tmp_dir):
        records = [generate_record("Flu")]
        path = write_v5_csv(records, tmp_dir, "Flu")
        content = path.read_text(encoding="utf-8")
        lines = (
            content.strip().split("\r\n")
            if "\r\n" in content
            else content.strip().split("\n")
        )
        assert len(lines) == 2
        assert lines[0].count("|") > 0

    def test_write_multiple_types(self, tmp_dir):
        for vtype in VACCINE_TYPES:
            records = [generate_record(vtype) for _ in range(3)]
            path = write_v5_csv(records, tmp_dir, vtype)
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            lines = (
                content.strip().split("\r\n")
                if "\r\n" in content
                else content.strip().split("\n")
            )
            assert len(lines) == 4


class TestGenerateDataset:
    def test_generate_dataset_default(self, tmp_dir):
        path = generate_dataset("Flu", num_records=10, output_dir=str(tmp_dir))
        assert path.exists()

    def test_generate_dataset_custom_org(self, tmp_dir):
        path = generate_dataset(
            "COVID", num_records=5, output_dir=str(tmp_dir), org_code="ORG999"
        )
        assert "ORG999" in path.name


class TestV5FieldsSpec:
    def test_v5_fields_match_generator(self):
        gen_fields = set(V5_FIELDS)
        spec_fields = {f["name"] for f in V5_FIELDS_SPEC}
        assert gen_fields == spec_fields

    def test_mandatory_fields_subset(self):
        for field in MANDATORY_FIELDS:
            assert field in V5_FIELDS

    def test_required_fields_subset(self):
        for field in REQUIRED_FIELDS:
            assert field in V5_FIELDS
