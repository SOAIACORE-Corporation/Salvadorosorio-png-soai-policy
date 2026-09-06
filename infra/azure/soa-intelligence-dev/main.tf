data "azurerm_client_config" "current" {}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
  numeric = true
}

resource "random_password" "postgresql" {
  length           = 32
  special          = true
  min_upper        = 2
  min_lower        = 2
  min_numeric      = 2
  min_special      = 2
  override_special = "!#$%&*+-.:=?@^_~"
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  required_tags = merge(
    var.tags,
    {
      project        = "SOA Intelligence"
      architecture   = "SOAiaCore"
      environment    = var.environment
      workstream     = "SOA-INTELLIGENCE-A2"
      managed_by     = "terraform"
      data_class     = "restricted"
      canonical_role = "persistence-dev"
    },
  )
}

resource "azurerm_resource_group" "soa_intelligence" {
  name     = "rg-${local.name_prefix}"
  location = var.location
  tags     = local.required_tags
}
