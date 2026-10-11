variable "name" {
  description = "Name prefix applied to every resource in this module."
  type        = string
}

variable "vpc_cidr" {
  description = "IPv4 CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) <= 20
    error_message = "vpc_cidr must be a valid CIDR with a prefix of /20 or shorter, so /20 subnets fit inside it."
  }
}

variable "public_subnet_count" {
  description = "How many public subnets to create, one per availability zone."
  type        = number
  default     = 3

  validation {
    condition     = var.public_subnet_count >= 2 && var.public_subnet_count <= 6
    error_message = "public_subnet_count must be between 2 and 6. EKS requires at least two AZs."
  }
}

variable "tags" {
  description = "Tags merged into every resource. Leave empty if the provider sets default_tags."
  type        = map(string)
  default     = {}
}