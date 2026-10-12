variable "cluster_name" {
  description = "Name of the EKS cluster."
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes minor version for the control plane. Always set explicitly — omitting it lets the provider pick, which makes the control plane version a function of provider version."
  type        = string

  validation {
    condition     = can(regex("^1\\.[0-9]{2}$", var.kubernetes_version))
    error_message = "kubernetes_version must be a minor version such as \"1.36\", not a patch version."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs for the control plane ENIs. At least two, in different availability zones."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "EKS requires subnets in at least two availability zones."
  }
}

variable "endpoint_public_access" {
  description = "Whether the Kubernetes API server is reachable from the internet."
  type        = bool
  default     = true
}

variable "public_access_cidrs" {
  description = "CIDR blocks permitted to reach the public API endpoint. 0.0.0.0/0 is open to the internet; narrow it to your own IP where practical."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "authentication_mode" {
  description = "API uses access entries only. API_AND_CONFIG_MAP also keeps the legacy aws-auth ConfigMap. CONFIG_MAP is legacy-only."
  type        = string
  default     = "API"

  validation {
    condition     = contains(["API", "API_AND_CONFIG_MAP", "CONFIG_MAP"], var.authentication_mode)
    error_message = "authentication_mode must be API, API_AND_CONFIG_MAP, or CONFIG_MAP."
  }
}

variable "bootstrap_cluster_creator_admin_permissions" {
  description = "Grant the IAM principal that creates the cluster admin access. Applied at creation only."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags merged into every resource. Leave empty if the provider sets default_tags."
  type        = map(string)
  default     = {}
}