variable "operator_ip_address" {
  description = "Operator public IPv4/CIDR allowed by the controlled-pilot Key Vault and evidence Storage firewall. Supply outside Git for an authorized plan."
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(trimspace(var.operator_ip_address)) > 0
    error_message = "operator_ip_address must be supplied outside source control."
  }
}

variable "oidc_client_id" {
  description = "Microsoft Entra confidential Web application client ID. Supply outside Git for an authorized plan."
  type        = string
  nullable    = false

  validation {
    condition     = length(trimspace(var.oidc_client_id)) > 0
    error_message = "oidc_client_id must be supplied outside source control."
  }
}

variable "oidc_client_secret" {
  description = "Microsoft Entra confidential Web application client secret. Supply only through an approved secret source; never commit it."
  type        = string
  sensitive   = true
  nullable    = false

  validation {
    condition     = length(var.oidc_client_secret) > 0
    error_message = "oidc_client_secret must be supplied outside source control."
  }
}
