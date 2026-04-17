variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-west-2"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "name_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "ducklake"
}

variable "vpc_id" {
  description = "VPC ID for deploying resources"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for RDS and ECS"
  type        = list(string)
}

variable "catalog_instance_class" {
  description = "RDS instance class for catalog PostgreSQL"
  type        = string
  default     = "db.t4g.micro"
}

variable "data_bucket_name" {
  description = "S3 bucket name for Parquet data files"
  type        = string
  default     = ""
}

variable "dbt_schedule" {
  description = "EventBridge schedule expression for dbt runs"
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "dbt_task_cpu" {
  description = "CPU units for dbt ECS task"
  type        = number
  default     = 1024
}

variable "dbt_task_memory" {
  description = "Memory (MB) for dbt ECS task"
  type        = number
  default     = 2048
}