variable "subscription_id" {
  description = "Azure subscription targeted by the authorized remote-state bootstrap. Supply outside Git."
  type        = string
  sensitive   = true
}

variable "location" {
  description = "Azure region for the dedicated Terraform state resource group and storage account."
  type        = string
  default     = "eastus2"
}

variable "resource_group_name" {
  description = "Exact dedicated resource group for Terraform remote state. Required explicitly to prevent accidental creation of a duplicate state store."
  type        = string

  validation {
    condition     = length(trimspace(var.resource_group_name)) > 0
    error_message = "resource_group_name must be supplied explicitly from verified Azure discovery."
  }
}

variable "storage_account_name" {
  description = "Exact globally unique Storage Account name for Terraform state. Supply the verified existing name when adopting an existing backend."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "storage_account_name must contain only lowercase letters and numbers and be 3-24 characters long."
  }
}

variable "container_name" {
  description = "Exact private Blob container used by the azurerm backend. Required explicitly after management/data-plane verification; do not invent or rename for cosmetic reasons."
  type        = string

  validation {
    condition     = length(trimspace(var.container_name)) > 0
    error_message = "container_name must be supplied explicitly from verified backend discovery."
  }
}

variable "retention_days" {
  description = "Soft-delete retention for Blob objects and containers."
  type        = number
  default     = 14

  validation {
    condition     = var.retention_days >= 7 && var.retention_days <= 365
    error_message = "retention_days must be between 7 and 365."
  }
}

variable "allowed_ip_ranges" {
  description = "Explicitly approved public IPv4/CIDR ranges permitted during bootstrap when no private operator path is available. Empty means deny-by-default except Azure service bypass."
  type        = set(string)
  default     = []
}

variable "private_link_access" {
  description = "Existing Storage firewall private-link access exceptions to preserve during adopt-first reconciliation. Supply only values verified from the authoritative Azure resource."
  type = list(object({
    endpoint_resource_id = string
    endpoint_tenant_id   = string
  }))
  default = []
}

variable "state_principal_object_ids" {
  description = "Microsoft Entra object IDs allowed to read/write Terraform state through RBAC."
  type        = set(string)
  default     = []
}

variable "tags" {
  description = "Additional governance tags for the remote-state resources."
  type        = map(string)
  default     = {}
}
