terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "nhs-ducklake-terraform-state"
    key    = "vaccination-lake/terraform.tfstate"
    region = "eu-west-2"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "duck-lakehouse"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}