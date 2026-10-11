variable "repository_name" {
  description = "Name of ECR repository."
  type        = string
}

variable "image_tag_mutability" {
  description = "IMMUTABLE prevents overwriting an existing tag. MUTABLE allows it."
  type        = string
  default     = "IMMUTABLE"

  validation {
    condition     = contains(["IMMUTABLE", "MUTABLE"], var.image_tag_mutability)
    error_message = "image_tag_mutability must be IMMUTABLE or MUTABLE."
  }
}

variable "scan_on_push" {
  description = "Run a basic vulnerability scan when an image is pushed."
  type        = bool
  default     = true
}

variable "untagged_expire_days" {
  description = "Days before an untagged image is expired. Untagged layers are invisible in the console and bill indefinitely."
  type        = number
  default     = 1
}

variable "max_tagged_images" {
  description = "Maximum number of images to retain. Oldest beyond this are expired."
  type        = number
  default     = 10
}

variable "force_delete" {
  description = "Allow terraform destroy to delete the repository even when it still contains images."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags merged into every resource. Leave empty if the provider sets default_tags."
  type        = map(string)
  default     = {}
}