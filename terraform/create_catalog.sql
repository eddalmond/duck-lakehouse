-- Create DuckLake catalog schema in PostgreSQL
-- Run this after Terraform provisions the RDS/Aurora instance

-- Create the database
CREATE DATABASE vaccination_lake;

-- Connect to the database, then DuckDB uses this as catalog:
-- ATTACH 'ducklake:pg:postgres://user:pass@host:5432/vaccination_lake' AS vaccination_lake
--   (DATA 's3://nhs-vaccination-lake-data/parquet');

-- DuckLake v1.0 will auto-create required catalog tables on ATTACH.
-- No manual schema creation needed in the PostgreSQL database.