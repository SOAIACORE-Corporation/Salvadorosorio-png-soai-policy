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
  description = "Dedicated resource group for Terraform remote state."
  type        = string
  default     = "rg-soaiacore-tfstate"
}

variable "storage_account_name" {
  description = "Globally unique Storage Account name for Terraform state. Lowercase letters and numbers only, 3-24 characters."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "storage_account_name must contain only lowercase letters and numbers and be 3-24 characters long."
  }
}

variable "container_name" {
  description = "Private Blob container used by the azurerm backend."
  type        = string
  default     = "tfstate"
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
