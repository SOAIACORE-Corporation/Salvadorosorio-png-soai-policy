# A2 private migration execution path.
# R1 design only until a governed saved plan and exact R2 execution gate exist.
# PostgreSQL remains private; this job reaches it from the same A2 VNet.

resource "azurerm_subnet" "container_apps" {
  name                 = "snet-container-apps"
  resource_group_name  = azurerm_resource_group.soa_intelligence.name
  virtual_network_name = azurerm_virtual_network.soa_intelligence.name
  address_prefixes     = ["10.60.20.0/27"]

  delegation {
    name = "container-apps-environment"

    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_log_analytics_workspace" "a2_migration" {
  name                = "log-${local.name_prefix}-migration"
  location            = azurerm_resource_group.soa_intelligence.location
  resource_group_name = azurerm_resource_group.soa_intelligence.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.required_tags
}

resource "azurerm_container_app_environment" "a2_migration" {
  name                       = "cae-${local.name_prefix}-migration"
  location                   = azurerm_resource_group.soa_intelligence.location
  resource_group_name        = azurerm_resource_group.soa_intelligence.name
  infrastructure_subnet_id   = azurerm_subnet.container_apps.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.a2_migration.id
  logs_destination           = "log-analytics"
  tags                       = local.required_tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_app_job" "a2_migration" {
  name                         = "caj-soaintelligence-dev-migrate"
  location                     = azurerm_resource_group.soa_intelligence.location
  resource_group_name          = azurerm_resource_group.soa_intelligence.name
  container_app_environment_id = azurerm_container_app_environment.a2_migration.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = 1800
  replica_retry_limit          = 0
  tags                         = local.required_tags

  secret {
    name  = "postgres-password"
    value = random_password.postgresql.result
  }

  secret {
    name  = "ghcr-token"
    value = var.ghcr_token
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = "ghcr-token"
  }

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name    = "a2-migration"
      image   = var.migration_worker_image
      cpu     = 0.25
      memory  = "0.5Gi"
      command = ["python", "-m", "soaiacore_worker", "a2-bootstrap"]

      env {
        name  = "SOAIACORE_PROVIDER_MODE"
        value = "MOCK"
      }

      env {
        name  = "POSTGRES_HOST"
        value = azurerm_postgresql_flexible_server.soa_intelligence.fqdn
      }

      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }

      env {
        name  = "POSTGRES_DB"
        value = azurerm_postgresql_flexible_server_database.soa_intelligence.name
      }

      env {
        name  = "POSTGRES_USER"
        value = var.postgresql_administrator_login
      }

      env {
        name        = "POSTGRES_PASSWORD"
        secret_name = "postgres-password"
      }
    }
  }

  depends_on = [
    azurerm_postgresql_flexible_server_configuration.extensions,
    azurerm_private_dns_zone_virtual_network_link.postgresql,
  ]
}
