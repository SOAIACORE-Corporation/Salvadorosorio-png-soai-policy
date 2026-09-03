data "azurerm_client_config" "current" {}

data "azurerm_monitor_action_group" "operations" {
  name                = "ag-soaiacore-p0-ops"
  resource_group_name = azurerm_resource_group.pilot.name
}

locals {
  oidc_issuer       = "https://login.microsoftonline.com/${data.azurerm_client_config.current.tenant_id}/v2.0"
  oidc_web_base_url = "https://ca-${local.name_prefix}-web-${random_string.suffix.result}.${azurerm_container_app_environment.pilot.default_domain}"
}

resource "random_password" "internal_auth" {
  length  = 48
  lower   = true
  numeric = true
  special = false
  upper   = true
}

resource "azurerm_subnet" "private_endpoints" {
  name                                          = "snet-private-endpoints"
  resource_group_name                           = azurerm_resource_group.pilot.name
  virtual_network_name                          = azurerm_virtual_network.pilot.name
  address_prefixes                              = ["10.42.1.16/28"]
  private_endpoint_network_policies             = "Disabled"
  private_link_service_network_policies_enabled = true
}

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = azurerm_resource_group.pilot.name
  tags                = local.required_tags
}

resource "azurerm_private_dns_zone" "key_vault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = azurerm_resource_group.pilot.name
  tags                = local.required_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "link-soaiacore-p0-blob"
  private_dns_zone_id   = azurerm_private_dns_zone.blob.id
  virtual_network_id    = azurerm_virtual_network.pilot.id
  registration_enabled  = false
  tags                  = local.required_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "key_vault" {
  name                  = "link-soaiacore-p0-key-vault"
  private_dns_zone_id   = azurerm_private_dns_zone.key_vault.id
  virtual_network_id    = azurerm_virtual_network.pilot.id
  registration_enabled  = false
  tags                  = local.required_tags
}

resource "azurerm_key_vault" "pilot" {
  name                          = "kv-${local.name_prefix}-${random_string.suffix.result}"
  location                      = azurerm_resource_group.pilot.location
  resource_group_name           = azurerm_resource_group.pilot.name
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 7
  public_network_access_enabled = true
  tags                          = local.required_tags

  network_acls {
    bypass                     = "AzureServices"
    default_action             = "Deny"
    ip_rules                   = [var.operator_ip_address]
    virtual_network_subnet_ids = []
  }
}

resource "azurerm_role_assignment" "operator_key_vault_secrets_officer" {
  scope                = azurerm_key_vault.pilot.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
  principal_type       = "User"
}

resource "azurerm_role_assignment" "workload_key_vault_secrets_user" {
  scope                = azurerm_key_vault.pilot.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.workload.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_key_vault_secret" "ghcr" {
  name         = "ghcr-pull-token"
  value        = var.ghcr_token
  key_vault_id = azurerm_key_vault.pilot.id

  depends_on = [azurerm_role_assignment.operator_key_vault_secrets_officer]
}

resource "azurerm_key_vault_secret" "internal_auth" {
  name         = "internal-auth-secret"
  value        = random_password.internal_auth.result
  key_vault_id = azurerm_key_vault.pilot.id

  depends_on = [azurerm_role_assignment.operator_key_vault_secrets_officer]
}

resource "azurerm_key_vault_secret" "oidc" {
  count = 1

  name         = "oidc-client-secret"
  value        = var.oidc_client_secret
  key_vault_id = azurerm_key_vault.pilot.id

  depends_on = [azurerm_role_assignment.operator_key_vault_secrets_officer]
}

resource "azurerm_key_vault_secret" "postgresql" {
  name         = "postgres-password"
  value        = random_password.postgresql.result
  key_vault_id = azurerm_key_vault.pilot.id

  depends_on = [azurerm_role_assignment.operator_key_vault_secrets_officer]
}

resource "azurerm_private_endpoint" "evidence_blob" {
  name                = "pe-${local.name_prefix}-blob-${random_string.suffix.result}"
  location            = azurerm_resource_group.pilot.location
  resource_group_name = azurerm_resource_group.pilot.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.required_tags

  private_service_connection {
    name                           = "psc-${local.name_prefix}-blob"
    private_connection_resource_id = azurerm_storage_account.evidence.id
    is_manual_connection           = false
    subresource_names              = ["blob"]
  }

  private_dns_zone_group {
    name                 = "blob"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

resource "azurerm_private_endpoint" "key_vault" {
  name                = "pe-${local.name_prefix}-key-vault-${random_string.suffix.result}"
  location            = azurerm_resource_group.pilot.location
  resource_group_name = azurerm_resource_group.pilot.name
  subnet_id           = azurerm_subnet.private_endpoints.id
  tags                = local.required_tags

  private_service_connection {
    name                           = "psc-${local.name_prefix}-key-vault"
    private_connection_resource_id = azurerm_key_vault.pilot.id
    is_manual_connection           = false
    subresource_names              = ["vault"]
  }

  private_dns_zone_group {
    name                 = "key-vault"
    private_dns_zone_ids = [azurerm_private_dns_zone.key_vault.id]
  }
}

resource "azurerm_monitor_metric_alert" "core_unavailable" {
  name                = "alrt-${local.name_prefix}-core-unavailable"
  resource_group_name = azurerm_resource_group.pilot.name
  scopes              = [azurerm_container_app.core.id]
  description         = "Controlled-pilot Core has no available replicas."
  severity            = 1
  enabled             = true
  auto_mitigate       = true
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.required_tags

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "Replicas"
    aggregation      = "Average"
    operator         = "LessThan"
    threshold        = 1
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.operations.id
  }
}

resource "azurerm_monitor_metric_alert" "web_unavailable" {
  name                = "alrt-${local.name_prefix}-web-unavailable"
  resource_group_name = azurerm_resource_group.pilot.name
  scopes              = [azurerm_container_app.web.id]
  description         = "Controlled-pilot Web has no available replicas."
  severity            = 1
  enabled             = true
  auto_mitigate       = true
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.required_tags

  criteria {
    metric_namespace = "Microsoft.App/containerApps"
    metric_name      = "Replicas"
    aggregation      = "Average"
    operator         = "LessThan"
    threshold        = 1
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.operations.id
  }
}

resource "azurerm_monitor_metric_alert" "worker_failed" {
  name                = "alrt-${local.name_prefix}-worker-failed"
  resource_group_name = azurerm_resource_group.pilot.name
  scopes              = [azurerm_container_app_job.worker.id]
  description         = "Controlled-pilot Worker reports a failed execution."
  severity            = 1
  enabled             = true
  auto_mitigate       = true
  frequency           = "PT1M"
  window_size         = "PT5M"
  tags                = local.required_tags

  criteria {
    metric_namespace = "Microsoft.App/jobs"
    metric_name      = "Executions"
    aggregation      = "Total"
    operator         = "GreaterThan"
    threshold        = 0

    dimension {
      name     = "state"
      operator = "Include"
      values   = ["Failed"]
    }
  }

  action {
    action_group_id = data.azurerm_monitor_action_group.operations.id
  }
}

resource "azurerm_consumption_budget_resource_group" "pilot" {
  name              = "budget-${local.name_prefix}"
  resource_group_id = azurerm_resource_group.pilot.id
  amount            = 25
  time_grain        = "Monthly"

  time_period {
    start_date = "2026-08-01T00:00:00Z"
    end_date   = "2027-08-01T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    threshold_type = "Actual"
    contact_groups = [data.azurerm_monitor_action_group.operations.id]
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    threshold_type = "Forecasted"
    contact_groups = [data.azurerm_monitor_action_group.operations.id]
  }
}
