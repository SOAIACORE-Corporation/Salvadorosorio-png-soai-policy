variable "subscription_id" {
  description = "Azure subscription targeted by an authorized P0 plan/apply. Never commit a real value."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
}

variable "location" {
  description = "Azure region validated for the P0 resource types."
  type        = string
  default     = "eastus2"
}

variable "project_name" {
  description = "Short project name used in resource names and tags."
  type        = string
  default     = "soaiacore"

  validation {
    condition     = can(regex("^[a-z0-9-]{3,20}$", var.project_name))
    error_message = "project_name must contain 3-20 lowercase letters, digits, or hyphens."
  }
}

variable "owner" {
  description = "Accountable owner recorded on every taggable resource."
  type        = string
  default     = "SOAIACORE"
}

variable "ttl_hours" {
  description = "Maximum lifetime of the disposable Provider Pilot after creation."
  type        = number
  default     = 168

  validation {
    condition     = var.ttl_hours > 0 && var.ttl_hours <= 168
    error_message = "ttl_hours must be between 1 and 168 for the P0 pilot."
  }
}

variable "expires_at" {
  description = "Explicit RFC3339 teardown deadline, supplied for every plan/apply (for example 2026-08-30T00:00:00Z)."
  type        = string

  validation {
    condition     = can(timecmp(var.expires_at, var.expires_at))
    error_message = "expires_at must be a valid RFC3339 timestamp."
  }
}

variable "core_image" {
  description = "Approved immutable Core API OCI image reference, preferably pinned by sha256 digest."
  type        = string

  validation {
    condition     = length(trimspace(var.core_image)) > 0
    error_message = "core_image must be an approved non-empty OCI image reference."
  }
}

variable "web_image" {
  description = "Approved immutable Web OCI image reference, preferably pinned by sha256 digest."
  type        = string

  validation {
    condition     = length(trimspace(var.web_image)) > 0
    error_message = "web_image must be an approved non-empty OCI image reference."
  }
}

variable "worker_image" {
  description = "Approved immutable Worker OCI image reference, preferably pinned by sha256 digest."
  type        = string

  validation {
    condition     = length(trimspace(var.worker_image)) > 0
    error_message = "worker_image must be an approved non-empty OCI image reference."
  }
}

variable "postgresql_administrator_login" {
  description = "Non-secret PostgreSQL administrator login for the disposable pilot."
  type        = string
  default     = "soaiadmin"
}

variable "github_repository" {
  description = "GitHub owner/repository allowed to federate as the pilot deployer."
  type        = string
  default     = "SOAIACORE-Corporation/Salvadorosorio-png-soai-policy"

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repository))
    error_message = "github_repository must use owner/repository format."
  }
}

variable "github_branch" {
  description = "Only branch authorized by the pilot deployer federated credential."
  type        = string
  default     = "rebuild/p0-v0.6-final"
}
