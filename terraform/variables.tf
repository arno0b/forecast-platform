variable "region" {
  description = "AWS region for all resource"
  type        = string
  default     = "ap-southeast-2"
}

variable "profile" {
  description = "AWS CLI profile for local runs"
  type        = string
  default     = "terraform"
  nullable    = true
}

variable "project_name" {
  description = "Project tag applied to every resource"
  type        = string
  default     = "forecast-platform"
}