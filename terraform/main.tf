provider "aws" {
  region  = var.region
  profile = var.profile

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}

resource "aws_ecr_registry_scanning_configuration" "this" {
  scan_type = "BASIC"

  rule {
    scan_frequency = "SCAN_ON_PUSH"
    repository_filter {
      filter      = "*"
      filter_type = "WILDCARD"
    }
  }
}


module "network" {
  source   = "./modules/network"
  name     = var.project_name
  vpc_cidr = "10.0.0.0/16"
}

module "ecr" {
  source = "./modules/ecr"

  repository_name = "forecast-platform"
}
data "aws_caller_identity" "current" {}

data "aws_region" "current" {}