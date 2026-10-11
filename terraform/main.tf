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

module "network" {
  source   = "./modules/network"
  name     = var.project_name
  vpc_cidr = "10.0.0.0/16"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}