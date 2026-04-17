# PostgreSQL catalog for DuckLake (RDS/Aurora Serverless v2)

resource "aws_db_subnet_group" "ducklake" {
  name       = "${var.name_prefix}-catalog"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "DuckLake Catalog DB Subnet Group"
  }
}

resource "aws_security_group" "catalog" {
  name        = "${var.name_prefix}-catalog-sg"
  description = "Security group for DuckLake PostgreSQL catalog"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "DuckLake Catalog Security Group"
  }
}

resource "aws_rds_cluster" "ducklake_catalog" {
  cluster_identifier = "${var.name_prefix}-catalog"
  engine             = "aurora-postgresql"
  engine_version     = "16.4"
  database_name     = "vaccination_lake"
  master_username   = "ducklake_admin"
  master_password   = var.catalog_password

  db_subnet_group_name   = aws_db_subnet_group.ducklake.name
  vpc_security_group_ids = [aws_security_group.catalog.id]

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 1.0
  }

  skip_final_snapshot = var.environment == "dev" ? true : false

  tags = {
    Name = "DuckLake PostgreSQL Catalog"
  }
}

resource "aws_rds_cluster_instance" "ducklake_catalog" {
  cluster_identifier  = aws_rds_cluster.ducklake_catalog.id
  instance_class      = "db.serverless"
  engine              = "aurora-postgresql"
  engine_version      = "16.4"

  tags = {
    Name = "DuckLake Catalog Instance"
  }
}

variable "catalog_password" {
  description = "Master password for catalog PostgreSQL (store in SSM)"
  type        = string
  sensitive   = true
}