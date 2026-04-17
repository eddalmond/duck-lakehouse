# Duck Lakehouse — AWS Expansion Architecture

This directory documents the AWS deployment path for Duck Lakehouse. The local
stack (DuckDB + SQLite catalog + filesystem data) maps directly to an AWS
deployment (DuckDB + PostgreSQL catalog + S3 data).

## Architecture: Local → AWS

| Component | Local | AWS |
|-----------|-------|-----|
| Catalog | SQLite file | PostgreSQL (RDS Aurora Serverless v2) |
| Data storage | Local filesystem | S3 bucket |
| MESH ingestion | File watcher (MESH simulator) | terraform-aws-mesh-client (Lambda + S3) |
| dbt execution | Local dbt-duckdb | ECS Fargate task (scheduled) |
| Orchestration | Makefile / scripts | Step Functions / EventBridge |

## Terraform Modules

### 1. terraform-aws-ducklake

Provisions the DuckLake infrastructure on AWS:

```hcl
module "ducklake" {
  source = "./terraform-aws-ducklake"

  name              = "vaccination-lake"
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids

  # PostgreSQL catalog
  catalog_instance_class = "db.t4g.micro"
  catalog_engine_version = "16.4"

  # S3 data bucket
  data_bucket_name = "nhs-vaccination-lake-data"

  # DuckDB version
  duckdb_version = "1.2.0"
}
```

**Resources created:**
- RDS PostgreSQL instance (or Aurora Serverless v2 cluster)
- S3 bucket for Parquet data files
- IAM policies for DuckDB ↔ S3 access
- Security groups for PostgreSQL access
- SSM parameters for connection strings

**DuckLake connection on AWS:**
```sql
ATTACH 'ducklake:pg:postgres://user:pass@ducklake-catalog.xxxxx.eu-west-2.rds.amazonaws.com:5432/vaccination_lake' AS vaccination_lake
(DATA 's3://nhs-vaccination-lake-data/parquet');
```

### 2. terraform-aws-mesh-client

Reuses the existing terraform-aws-mesh-client pattern for MESH integration:

```hcl
module "mesh_client" {
  source = "git::https://github.com/NHSDigital/terraform-aws-mesh-client.git?ref=v2.0"

  name                = "vaccination-mesh"
  mesh_mailbox_id     = "VACCINATION_MESH_MAILBOX"
  mesh_password_ssm   = "/mesh/vaccination/password"

  # S3 destination for processed files
  destination_bucket  = module.ducklake.data_bucket
  destination_prefix  = "mesh/inbox/"
}
```

**Resources created:**
- Lambda function for MESH message processing
- S3 event notification to trigger ingestion Lambda
- DLQ (Dead Letter Queue) for failed messages
- CloudWatch alarms and logs

### 3. terraform-aws-dbt-runner

Scheduled dbt execution on ECS Fargate:

```hcl
module "dbt_runner" {
  source = "./terraform-aws-dbt-runner"

  name = "vaccination-dbt"

  # dbt project stored in S3
  dbt_project_bucket = "nhs-vaccination-dbt-code"
  dbt_project_key    = "dbt_project.tar.gz"

  # DuckLake connection
  ducklake_catalog_host = module.ducklake.catalog_endpoint
  ducklake_catalog_port = 5432
  ducklake_data_path    = "s3://nhs-vaccination-lake-data/parquet"

  # Schedule
  schedule_expression = "cron(0 6 * * ? *)"  # 6am UTC daily

  # ECS configuration
  vpc_id            = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  task_cpu          = 1024
  task_memory       = 2048
}
```

**Resources created:**
- ECS task definition for dbt-duckdb
- CloudWatch EventBridge rule (schedule)
- ECS cluster
- IAM role for S3 + PostgreSQL + SSM access
- CloudWatch log group

## Deployment Steps

### 1. Infrastructure (Terraform)

```bash
cd terraform/
terraform init
terraform plan
terraform apply
```

### 2. Database Setup

```bash
# Connect to PostgreSQL and create catalog
psql $DATABASE_URL -f create_catalog.sql
```

### 3. MESH Configuration

```bash
# Configure MESH mailbox credentials
aws ssm put-parameter --name "/mesh/vaccination/password" \
  --value "$MESH_PASSWORD" --type SecureString
```

### 4. dbt Deployment

```bash
# Package dbt project
cd duck_lakehouse/dbt/dbt_ducklake
tar czf dbt_project.tar.gz .
aws s3 cp dbt_project.tar.gz s3://nhs-vaccination-dbt-code/
```

### 5. Verification

```bash
# Trigger a manual dbt run
aws ecs run-task --task-definition vaccination-dbt-task --cluster vaccination-cluster
```

## Security Considerations

- PostgreSQL catalog: encrypt at rest, VPC-only access
- S3 data: server-side encryption (SSE-S3 or SSE-KMS)
- MESH credentials: stored in SSM Parameter Store (SecureString)
- dbt runner: no public IP, runs in private subnet
- IAM least-privilege: each component has minimal required permissions

## Cost Estimates (Monthly, eu-west-2)

| Resource | Specification | Estimated Cost |
|----------|--------------|----------------|
| Aurora Serverless v2 | 0.5 ACU average | ~$25 |
| S3 storage | 10 GB Parquet | ~$0.25 |
| ECS Fargate | 1 vCPU, 2 GB, 1hr/day | ~$5 |
| CloudWatch | Logs + Metrics | ~$5 |
| **Total** | | **~$35/month** |

## Data Flow on AWS

```
NHSE Supplier → MESH → S3 (inbox) → Lambda → DuckLake (S3 + PostgreSQL)
                                                   ↓
                                          EventBridge (schedule)
                                                   ↓
                                            ECS (dbt run)
                                                   ↓
                                          DuckLake marts
                                                   ↓
                                          Athena / QuickSight
```

## References

- [DuckLake Documentation](https://ducklake.select/docs/)
- [terraform-aws-mesh-client](https://github.com/NHSDigital/terraform-aws-mesh-client)
- [dbt-duckdb Adapter](https://github.com/duckdb/dbt-duckdb)
- [NHS MESH API](https://digital.nhs.uk/developer/api-collections/message-exchange-for-social-care-and-health-api)