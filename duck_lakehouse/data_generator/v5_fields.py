"""
V5 field definitions and validation reference.

Source: NHSE Daily Vaccination Events (In-Bound) Extract Technical
        Specification v5.1 FINAL
"""

V5_FIELDS = [
    {"pos": 1, "name": "NHS_NUMBER", "type": "String", "length": 10, "required": "R"},
    {"pos": 2, "name": "PERSON_FORENAME", "type": "String", "required": "M"},
    {"pos": 3, "name": "PERSON_SURNAME", "type": "String", "required": "M"},
    {"pos": 4, "name": "PERSON_DOB", "type": "Date", "format": "YYYYMMDD", "required": "M"},
    {"pos": 5, "name": "PERSON_GENDER_CODE", "type": "String", "values": ["0", "1", "2", "9"], "required": "M"},
    {"pos": 6, "name": "PERSON_POSTCODE", "type": "String", "length": "Up to 8", "required": "M"},
    {"pos": 7, "name": "DATE_AND_TIME", "type": "DateTime", "format": "YYYYMMDDThhmmsszz", "required": "M"},
    {"pos": 8, "name": "SITE_CODE", "type": "String", "required": "M"},
    {"pos": 9, "name": "SITE_CODE_TYPE_URI", "type": "String", "required": "M"},
    {"pos": 10, "name": "UNIQUE_ID", "type": "String", "required": "M"},
    {"pos": 11, "name": "UNIQUE_ID_URI", "type": "String", "required": "M"},
    {"pos": 12, "name": "ACTION_FLAG", "type": "String", "values": ["new", "update", "delete"], "required": "M"},
    {"pos": 13, "name": "PERFORMING_PROFESSIONAL_FORENAME", "type": "String", "required": "O"},
    {"pos": 14, "name": "PERFORMING_PROFESSIONAL_SURNAME", "type": "String", "required": "O"},
    {"pos": 15, "name": "RECORDED_DATE", "type": "Date", "format": "YYYYMMDD", "required": "M"},
    {"pos": 16, "name": "PRIMARY_SOURCE", "type": "Boolean", "values": ["TRUE", "FALSE"], "required": "M"},
    {"pos": 17, "name": "VACCINATION_PROCEDURE_CODE", "type": "String", "format": "SNOMED-CT", "required": "M"},
    {"pos": 18, "name": "VACCINATION_PROCEDURE_TERM", "type": "String", "format": "SNOMED-CT", "required": "R"},
    {"pos": 19, "name": "DOSE_SEQUENCE", "type": "String", "values": ["1", "2", "3", "4", "5", "6", "7", "8", "9"], "required": "R"},
    {"pos": 20, "name": "VACCINE_PRODUCT_CODE", "type": "String", "format": "dm+d SNOMED-CT", "required": "R"},
    {"pos": 21, "name": "VACCINE_PRODUCT_TERM", "type": "String", "format": "dm+d SNOMED-CT", "required": "R"},
    {"pos": 22, "name": "VACCINE_MANUFACTURER", "type": "String", "required": "R"},
    {"pos": 23, "name": "BATCH_NUMBER", "type": "String", "length": "max 100", "required": "R"},
    {"pos": 24, "name": "EXPIRY_DATE", "type": "String", "format": "YYYYMMDD", "required": "R"},
    {"pos": 25, "name": "SITE_OF_VACCINATION_CODE", "type": "String", "format": "SNOMED-CT", "required": "R"},
    {"pos": 26, "name": "SITE_OF_VACCINATION_TERM", "type": "String", "format": "SNOMED-CT", "required": "R"},
    {"pos": 27, "name": "ROUTE_OF_VACCINATION_CODE", "type": "String", "format": "SNOMED-CT", "required": "R"},
    {"pos": 28, "name": "ROUTE_OF_VACCINATION_TERM", "type": "String", "format": "SNOMED-CT", "required": "R"},
    {"pos": 29, "name": "DOSE_AMOUNT", "type": "String", "format": "Decimal (max 4)", "required": "R"},
    {"pos": 30, "name": "DOSE_UNIT_CODE", "type": "String", "format": "dm+d SNOMED-CT", "required": "R"},
    {"pos": 31, "name": "DOSE_UNIT_TERM", "type": "String", "format": "dm+d SNOMED-CT", "required": "R"},
    {"pos": 32, "name": "INDICATION_CODE", "type": "String", "format": "SNOMED-CT", "required": "R"},
    {"pos": 33, "name": "LOCATION_CODE", "type": "String", "required": "M"},
    {"pos": 34, "name": "LOCATION_CODE_TYPE_URI", "type": "String", "required": "M"},
]

MANDATORY_FIELDS = [f["name"] for f in V5_FIELDS if f["required"] == "M"]
REQUIRED_FIELDS = [f["name"] for f in V5_FIELDS if f["required"] in ("M", "R")]