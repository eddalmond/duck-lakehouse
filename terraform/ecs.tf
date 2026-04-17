# ECS task for scheduled dbt runs

resource "aws_ecs_cluster" "dbt_runner" {
  name = "${var.name_prefix}-dbt-cluster"

  tags = {
    Name = "DuckLake dbt Runner Cluster"
  }
}

resource "aws_ecs_task_definition" "dbt" {
  family                   = "${var.name_prefix}-dbt-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.dbt_task_cpu
  memory                   = var.dbt_task_memory

  execution_role_arn = aws_iam_role.dbt_execution.arn
  task_role_arn      = aws_iam_role.dbt_task.arn

  container_definitions = jsonencode([
    {
      name      = "dbt-runner"
      image     = "${var.dbt_ecr_repository != "" ? var.dbt_ecr_repository : "python:3.12-slim"}"
      essential = true

      command = [
        "sh", "-c",
        "pip install dbt-duckdb && dbt run --profiles-dir /app/profiles && dbt test --profiles-dir /app/profiles"
      ]

      environment = [
        { name = "DBT_PROJECT_DIR", value = "/app/dbt_project" },
        { name = "DUCKLAKE_CATALOG_HOST", value = aws_rds_cluster.ducklake_catalog.endpoint },
        { name = "DUCKLAKE_DATA_PATH", value = "s3://${aws_s3_bucket.ducklake_data.id}/parquet" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.name_prefix}-dbt"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "dbt"
        }
      }
    }
  ])

  tags = {
    Name = "DuckLake dbt Task Definition"
  }
}

variable "dbt_ecr_repository" {
  description = "ECR repository URL for custom dbt image (leave empty for default)"
  type        = string
  default     = ""
}

# CloudWatch log group for dbt
resource "aws_cloudwatch_log_group" "dbt" {
  name              = "/ecs/${var.name_prefix}-dbt"
  retention_in_days = 30

  tags = {
    Name = "DuckLake dbt Logs"
  }
}

# EventBridge schedule
resource "aws_scheduler_schedule" "dbt_run" {
  name = "${var.name_prefix}-dbt-schedule"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = var.dbt_schedule

  target {
    arn      = aws_ecs_cluster.dbt_runner.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.dbt.arn
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = var.private_subnet_ids
        security_groups  = [aws_security_group.catalog.id]
      }
    }
  }
}

# IAM roles
resource "aws_iam_role" "dbt_execution" {
  name = "${var.name_prefix}-dbt-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role" "dbt_task" {
  name = "${var.name_prefix}-dbt-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "dbt_s3" {
  name = "${var.name_prefix}-dbt-s3"
  role = aws_iam_role.dbt_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.ducklake_data.arn,
          "${aws_s3_bucket.ducklake_data.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "scheduler" {
  name = "${var.name_prefix}-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_ecs" {
  name = "${var.name_prefix}-scheduler-ecs"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecs:RunTask",
        "iam:PassRole"
      ]
      Resource = "*"
    }]
  })
}