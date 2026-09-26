terraform {
  required_version = "~> 1.16"

  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }

  backend "s3" {
    bucket       = "fp-tfstate-767398149699-apse2"
    key          = "forecast-platform/infra.tfstate"
    region       = "ap-southeast-2"
    profile      = "terraform"
    use_lockfile = true
  }
}