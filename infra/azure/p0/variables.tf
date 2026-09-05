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
  description = "Approved immutable Core API GHCR image reference pinned to the EXEC-03 sha256 digest."
  type        = string

  validation {
    condition     = var.core_image == "ghcr.io/soaiacore-corporation/soaiacore-core@sha256:8dae834b15be70f08ad82171ee785d01798e9bd3e7760942de49bf4060b9bf64"
    error_message = "core_image must equal the exact approved EXEC-03 digest reference."
  }
}

variable "web_image" {
  description = "Approved immutable Web GHCR image reference pinned to the EXEC-03 sha256 digest."
  type        = string

  validation {
    condition     = var.web_image == "ghcr.io/soaiacore-corporation/soaiacore-web@sha256:3302541a1f237a38ab9adffc958df8b8b6e8ec50ed6991d784e35ff2e0cd96f1"
    error_message = "web_image must equal the exact approved EXEC-03 digest reference."
  }
}

variable "worker_image" {
  description = "Approved immutable Worker GHCR image reference pinned to the EXEC-03 sha256 digest."
  type        = string

  validation {
    condition     = var.worker_image == "ghcr.io/soaiacore-corporation/soaiacore-worker@sha256:26513cc25d4544ed5468e34e3a7310ca36db57b20d8bd5ae123381a2f5155bb4"
    error_message = "worker_image must equal the exact approved EXEC-03 digest reference."
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
  description = "GitHub owner/repository allowed to federate as the pilot deployer. Case must match the observed GitHub OIDC repository claim."
  type        = string
  default     = "SOAIACORE-Corporation/Salvadorosorio-png-soai-policy"

  validation {
    condition     = var.github_repository == "SOAIACORE-Corporation/Salvadorosorio-png-soai-policy"
    error_message = "github_repository must equal the empirically observed GitHub OIDC repository claim."
  }
}

variable "github_environment" {
  description = "Only protected GitHub Environment authorized by the deployer federated credential."
  type        = string
  default     = "production"

  validation {
    condition     = var.github_environment == "production"
    error_message = "github_environment must remain exactly production for the P0 deploy trust boundary."
  }
}
