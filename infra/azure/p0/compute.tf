resource "azurerm_log_analytics_workspace" "pilot" {
  name                = "log-${local.name_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.pilot.location
  resource_group_name = azurerm_resource_group.pilot.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.required_tags
}

resource "azurerm_container_app_environment" "pilot" {
  name                       = "cae-${local.name_prefix}-${random_string.suffix.result}"
  location                   = azurerm_resource_group.pilot.location
  resource_group_name        = azurerm_resource_group.pilot.name
  infrastructure_subnet_id   = azurerm_subnet.container_apps.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.pilot.id
  logs_destination           = "log-analytics"
  tags                       = local.required_tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_app" "core" {
  name                         = "ca-${local.name_prefix}-core-${random_string.suffix.result}"
  container_app_environment_id = azurerm_container_app_environment.pilot.id
  workload_profile_name        = "Consumption"
  resource_group_name          = azurerm_resource_group.pilot.name
  revision_mode                = "Single"
  tags                         = local.required_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  secret {
    name  = "postgres-password"
    value = random_password.postgresql.result
  }

  secret {
    name  = local.ghcr_secret_name
    value = var.ghcr_token
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = local.ghcr_secret_name
  }

  ingress {
    external_enabled = false
    target_port      = 8000
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "core"
      image  = var.core_image
      cpu    = 0.25
      memory = "0.5Gi"

      liveness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health/live"
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health/ready"
        interval_seconds        = 15
        timeout                 = 5
        failure_count_threshold = 3
      }

      env {
        name  = "PYTHONPATH"
        value = "/app/.venv/lib/python3.12/site-packages"
      }

      env {
        name  = "SOAIACORE_PROVIDER_MODE"
        value = "MOCK"
      }

      env {
        name  = "SOAIACORE_DISPATCH_MODE"
        value = "AZURE"
      }

      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = var.subscription_id
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = azurerm_user_assigned_identity.workload.client_id
      }

      env {
        name  = "AZURE_RESOURCE_GROUP"
        value = azurerm_resource_group.pilot.name
      }

      env {
        name  = "AZURE_CONTAINER_APP_JOB_NAME"
        value = azurerm_container_app_job.worker.name
      }

      env {
        name  = "POSTGRES_HOST"
        value = local.database_host
      }

      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }

      env {
        name  = "POSTGRES_DB"
        value = local.database_name
      }

      env {
        name  = "POSTGRES_USER"
        value = var.postgresql_administrator_login
      }

      env {
        name        = "POSTGRES_PASSWORD"
        secret_name = "postgres-password"
      }

      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.evidence.name
      }

      env {
        name  = "AZURE_STORAGE_CONTAINER_NAME"
        value = azurerm_storage_container.evidence.name
      }
    }
  }
}

resource "azurerm_container_app" "web" {
  name                         = "ca-${local.name_prefix}-web-${random_string.suffix.result}"
  container_app_environment_id = azurerm_container_app_environment.pilot.id
  workload_profile_name        = "Consumption"
  resource_group_name          = azurerm_resource_group.pilot.name
  revision_mode                = "Single"
  tags                         = local.required_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  secret {
    name  = local.ghcr_secret_name
    value = var.ghcr_token
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = local.ghcr_secret_name
  }

  ingress {
    external_enabled = true
    target_port      = 3000
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "web"
      image  = var.web_image
      cpu    = 0.25
      memory = "0.5Gi"

      liveness_probe {
        transport               = "HTTP"
        port                    = 3000
        path                    = "/api/health/live"
        interval_seconds        = 30
        timeout                 = 5
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 3000
        path                    = "/api/health/ready"
        interval_seconds        = 15
        timeout                 = 5
        failure_count_threshold = 3
      }

      env {
        name  = "SOAIACORE_PROVIDER_MODE"
        value = "MOCK"
      }

      env {
        name  = "CORE_API_BASE_URL"
        value = "https://${azurerm_container_app.core.ingress[0].fqdn}"
      }
    }
  }
}

resource "azurerm_container_app_job" "worker" {
  name                         = "caj-${local.name_prefix}-worker-${random_string.suffix.result}"
  location                     = azurerm_resource_group.pilot.location
  resource_group_name          = azurerm_resource_group.pilot.name
  container_app_environment_id = azurerm_container_app_environment.pilot.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = 1800
  replica_retry_limit          = 1
  tags                         = local.required_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.workload.id]
  }

  secret {
    name  = "postgres-password"
    value = random_password.postgresql.result
  }

  secret {
    name  = local.ghcr_secret_name
    value = var.ghcr_token
  }

  registry {
    server               = "ghcr.io"
    username             = var.ghcr_username
    password_secret_name = local.ghcr_secret_name
  }

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "worker"
      image  = var.worker_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "PYTHONPATH"
        value = "/app/.venv/lib/python3.12/site-packages"
      }

      env {
        name  = "SOAIACORE_PROVIDER_MODE"
        value = "MOCK"
      }

      env {
        name  = "POSTGRES_HOST"
        value = local.database_host
      }

      env {
        name  = "POSTGRES_PORT"
        value = "5432"
      }

      env {
        name  = "POSTGRES_DB"
        value = local.database_name
      }

      env {
        name  = "POSTGRES_USER"
        value = var.postgresql_administrator_login
      }

      env {
        name        = "POSTGRES_PASSWORD"
        secret_name = "postgres-password"
      }

      env {
        name  = "AZURE_STORAGE_ACCOUNT_NAME"
        value = azurerm_storage_account.evidence.name
      }

      env {
        name  = "AZURE_STORAGE_CONTAINER_NAME"
        value = azurerm_storage_container.evidence.name
      }
    }
  }
}
