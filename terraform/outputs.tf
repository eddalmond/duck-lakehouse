# Outputs

output "catalog_endpoint" {
  description = "PostgreSQL catalog endpoint"
  value       = aws_rds_cluster.ducklake_catalog.endpoint
}

output "data_bucket_arn" {
  description = "S3 data bucket ARN"
  value       = aws_s3_bucket.ducklake_data.arn
}

output "data_bucket_name" {
  description = "S3 data bucket name"
  value       = aws_s3_bucket.ducklake_data.id
}

output "ecs_cluster_name" {
  description = "ECS cluster for dbt runs"
  value       = aws_ecs_cluster.dbt_runner.name
}

output "dbt_task_definition_arn" {
  description = "dbt ECS task definition ARN"
  value       = aws_ecs_task_definition.dbt.arn
}