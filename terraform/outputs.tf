output "account_id" {
  description = "AWS account Terraform is operating in"
  value       = data.aws_caller_identity.current.account_id
}

output "caller_arn" {
  description = "Identity Terraform authenticated as"
  value       = data.aws_caller_identity.current.arn
}

output "region" {
  value = data.aws_region.current.region
}

output "vpc_id" {
  description = "ID of the VPC."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs, one per availability zone."
  value       = module.network.public_subnet_ids
}

output "availability_zones" {
  description = "Availability zones the public subnets were placed in."
  value       = module.network.availability_zones
}

output "ecr_repository_url" {
  description = "ECR repository URL for the application image."
  value       = module.ecr.repository_url
}