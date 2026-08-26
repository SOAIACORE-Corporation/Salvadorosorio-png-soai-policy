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
  description = "Approved immutable Core API GHCR image reference pinned to the P0 sha256 digest."
  type        = string

  validation {
    condition     = var.core_image == "ghcr.io/soaiacore-corporation/soaiacore-core@sha256:e6564cad60afa7f7e1828c193c3512c7f1b0ce53aed26459e0a61b8ac33fb467"
    error_message = "core_image must equal the exact approved P0 digest reference."
  }
}

variable "web_image" {
  description = "Approved immutable Web GHCR image reference pinned to the P0 sha256 digest."
  type        = string

  validation {
    condition     = var.web_image == "ghcr.io/soaiacore-corporation/soaiacore-web@sha256:da26fd8bcf6cb2a4c242d380a28c682b19c6f094f0a898258a727ef558fa6c58"
    error_message = "web_image must equal the exact approved P0 digest reference."
  }
}

variable "worker_image" {
  description = "Approved immutable Worker GHCR image reference pinned to the P0 sha256 digest."
  type        = string

  validation {
    condition     = var.worker_image == "ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:971dc02fd1ba2306cd6e1d4864e8d7de0d447169256f7d89071bc5c94ccde9a1"
    error_message = "worker_image must equal the exact approved P0 digest reference."
  }
}

variable "ghcr_username" {
  description = "GitHub account name whose P0 pull credential has read access to the three approved private GHCR packages."
  type        = string

  validation {
    condition     = length(trimspace(var.ghcr_username)) > 0
    error_message = "ghcr_username must be supplied outside source control."
  }
}

variable "ghcr_token" {
  description = "Short-lived GitHub PAT classic with read:packages only, supplied outside Git for private GHCR pulls."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.ghcr_token) >= 1
    error_message = "ghcr_token must be supplied outside source control."
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
