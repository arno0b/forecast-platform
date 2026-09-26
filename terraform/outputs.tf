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