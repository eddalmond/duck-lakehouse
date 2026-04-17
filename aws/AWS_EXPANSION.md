# AWS Expansion Path

This document describes how to migrate the Duck Lakehouse PoC from local
execution to a production AWS deployment.

## Architecture Overview

| Component   | Local (PoC)             | AWS (Production)                    |
|-------------|--------------------------|-------------------------------------|
| Catalog     | DuckDB file              | PostgreSQL (RDS / Aurora)           |
| Data        | Local filesystem         | S3                                  |
| Ingestion   | MESH simulator (file)   | terraform-aws-mesh-client (Lambda)  |
| Compute     | DuckDB CLI              | DuckDB via Lambda / ECS / EMR       |
| Orchestration| Manual / script         | Step Functions / Airflow            |
| dbt         | dbt-duckdb local        | dbt-duckdb on ECS Fargate           |

## 1. DuckLake Catalog Migration

DuckLake supports multiple catalog backends. The DuckDB file catalog used in
the PoC can be migrated to PostgreSQL:

```sql
-- Local (PoC)
ATTACH 'ducklake:vaccination_lake.ducklake' AS vaccination_lake;

-- AWS (Production)
ATTACH 'ducklake:postgresql://user:pass@rds-host:5432/ducklake' AS vaccination_lake
  (DATA 's3://my-bucket/vaccination-lake/data');
```

### Terraform: RDS PostgreSQL for Catalog

```hcl
resource "aws_db_subnet_group" "ducklake" {
  name       = "ducklake-catalog"
  subnet_ids = var.private_subnet_ids

  tags = { Name = "ducklake-catalog" }
}

resource "aws_db_instance" "ducklake_catalog" {
  identifier           = "ducklake-catalog"
  engine               = "postgres"
  engine_version       = "16"
  instance_class       = "db.t4g.micro"
  allocated_storage    = 20
  db_name              = "ducklake"
  username             = "ducklake_admin"
  password             = var.db_password
  db_subnet_group_name = aws_db_subnet_group.ducklake.name
  vpc_security_group_ids = [aws_security_group.ducklake_rds.id]
  skip_final_snapshot  = false
  final_snapshot_identifier = "ducklake-catalog-final"
  backup_retention_period = 7

  tags = { Name = "ducklake-catalog" }
}
```

## 2. Data Storage Migration: Local to S3

```hcl
resource "aws_s3_bucket" "ducklake_data" {
  bucket = "ducklake-vaccination-data"

  tags = { Name = "ducklake-vaccination-data" }
}

resource "aws_s3_bucket_lifecycle_configuration" "ducklake" {
  bucket = aws_s3_bucket.ducklake_data.id

  rule {
    id     = "archive-old-data"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
  }
}
```

## 3. MESH Integration (terraform-aws-mesh-client)

The local MESH simulator is replaced by the terraform-aws-mesh-client module,
which uses Lambda functions triggered by S3 events:

```hcl
module "mesh_client" {
  source = "github.com/NHSDigital/terraform-aws-mesh-client"

  mesh_url              = var.mesh_url
  mesh_mailbox_id       = var.mesh_mailbox_id
  mesh_client_cert      = var.mesh_client_cert
  mesh_client_key       = var.mesh_client_key
  mesh_ca_cert          = var.mesh_ca_cert

  s3_bucket_inbound     = aws_s3_bucket.mesh_inbound.id
  s3_bucket_outbound    = aws_s3_bucket.mesh_outbound.id
  s3_bucket_processed   = aws_s3_bucket.mesh_processed.id

  lambda_function_name  = "mesh-client-handler"
  lambda_runtime        = "python3.11"
  lambda_timeout        = 300

  cloudwatch_log_group  = "/aws/lambda/mesh-client-handler"

  tags = var.tags
}
```

### MESH Inbound Flow (AWS)

```
NHS MESH → Lambda (terraform-aws-mesh-client) → S3 inbound/
  → S3 Event → Lambda (ingest_to_ducklake) → DuckLake staging
  → S3 Event → Lambda (archive) → S3 processed/
```

```hcl
resource "aws_lambda_function" "ingest_to_ducklake" {
  function_name = "ingest-to-ducklake"
  runtime       = "python3.11"
  handler       = "handler.lambda_handler"
  role          = aws_iam_role.ingest_role.arn
  timeout       = 300
  memory_size   = 512

  environment {
    variables = {
      DUCKLAKE_CATALOG = "postgresql://..."
      DUCKLAKE_DATA    = "s3://..."
    }
  }

  s3_key = "lambda/ingest_to_ducklake.zip"
}

resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowS3Invoke"
  function_name = aws_lambda_function.ingest_to_ducklake.function_name
  action        = "lambda:InvokeFunction"
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.mesh_inbound.arn
}
```

## 4. dbt on AWS (ECS Fargate)

```hcl
resource "aws_ecs_task_definition" "dbt_run" {
  family                   = "dbt-ducklake-run"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"

  container_definitions = jsonencode([{
    name      = "dbt"
    image     = "${var.ecr_repository_url}:latest"
    essential = true

    environment = [
      { name = "DBT_PROFILES_DIR", value = "/usr/app" },
    ]

    secrets = [
      { name = "DUCKLAKE_CATALOG_URL", valueFrom = var.catalog_url_param },
    ]
  }])
}

resource "aws_ecs_cluster" "ducklake" {
  name = "ducklake-dbt"
}
```

## 5. Orchestration (Step Functions)

```hcl
resource "aws_cloudwatch_event_rule" "mesh_inbound" {
  name                = "mesh-inbound-trigger"
  event_pattern       = jsonencode({
    source      = ["aws.s3"]
    detail_type = ["Object Created"]
    detail = {
      bucket = { name = [aws_s3_bucket.mesh_inbound.id] }
    }
  })
}

resource "aws_cloudwatch_event_target" "step_functions" {
  rule      = aws_cloudwatch_event_rule.mesh_inbound.name
  target_id = "TriggerStepFunction"
  arn       = aws_sfn_state_machine.ingest_pipeline.arn
}

resource "aws_sfn_state_machine" "ingest_pipeline" {
  name     = "ingest-pipeline"
  role_arn = aws_iam_role.step_functions.arn

  definition = jsonencode({
    StartAt = "IngestMESHData"
    States = {
      IngestMESHData = {
        Type  = "Task"
        Resource = aws_lambda_function.ingest_to_ducklake.arn
        Next  = "RunDBT"
      }
      RunDBT = {
        Type     = "Task"
        Resource = "arn:aws:states:::ecs:runTaskAndWait"
        Parameters = {
          TaskDefinition = aws_ecs_task_definition.dbt_run.arn
          Cluster       = aws_ecs_cluster.ducklake.arn
        }
        End = true
      }
    }
  })
}
```

## 6. Networking & Security

```hcl
resource "aws_security_group" "ducklake_rds" {
  name        = "ducklake-rds"
  description = "RDS access for DuckLake catalog"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_kms_key" "ducklake" {
  description = "DuckLake encryption key"
  tags = { Name = "ducklake" }
}
```

## 7. Monitoring

```hcl
resource "aws_cloudwatch_log_group" "ducklake" {
  name              = "/ducklake"
  retention_in_days = 30
}

resource "aws_cloudwatch_metric_alarm" "ingest_errors" {
  alarm_name          = "ducklake-ingest-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "300"
  statistic           = "Sum"
  threshold           = "5"
  alarm_description   = "Ingestion Lambda errors"
  dimensions = {
    FunctionName = aws_lambda_function.ingest_to_ducklake.function_name
  }
}
```

## Migration Checklist

- [ ] Deploy RDS PostgreSQL for DuckLake catalog
- [ ] Create S3 bucket for DuckLake data storage
- [ ] Configure terraform-aws-mesh-client for inbound MESH flow
- [ ] Deploy ingest Lambda (pipe-delimited CSV → DuckLake staging)
- [ ] Set up S3 event notifications for Lambda triggers
- [ ] Deploy dbt-duckdb ECS task definition
- [ ] Create Step Functions state machine for pipeline orchestration
- [ ] Configure CloudWatch alarms and log groups
- [ ] Test end-to-end: MESH → S3 → Lambda → DuckLake → dbt → marts
- [ ] Validate v5 spec compliance in production