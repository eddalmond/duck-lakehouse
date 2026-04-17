# S3 bucket for DuckLake Parquet data storage

resource "aws_s3_bucket" "ducklake_data" {
  bucket = var.data_bucket_name != "" ? var.data_bucket_name : "${var.name_prefix}-${var.environment}-data"

  tags = {
    Name = "DuckLake Data Storage"
  }
}

resource "aws_s3_bucket_versioning" "ducklake_data" {
  bucket = aws_s3_bucket.ducklake_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ducklake_data" {
  bucket = aws_s3_bucket.ducklake_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "ducklake_data" {
  bucket = aws_s3_bucket.ducklake_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "ducklake_data" {
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