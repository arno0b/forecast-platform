output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.this.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs, ordered by availability zone."
  value       = [for az in local.azs : aws_subnet.public[az].id]
}

output "availability_zones" {
  description = "Availability zones the public subnets were placed in."
  value       = local.azs
}

output "public_route_table_id" {
  description = "ID of the shared public route table."
  value       = aws_route_table.public.id
}