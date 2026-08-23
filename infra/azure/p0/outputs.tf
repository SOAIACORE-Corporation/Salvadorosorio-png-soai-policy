output "resource_group_name" {
  description = "Disposable P0 resource-group boundary."
  value       = azurerm_resource_group.pilot.name
}

output "deployer_client_id" {
  description = "Client ID of the GitHub OIDC deployer identity."
  value       = azurerm_user_assigned_identity.deployer.client_id
}

output "workload_client_id" {
  description = "Client ID used by Core, Web, and Worker."
  value       = azurerm_user_assigned_identity.workload.client_id
}

output "web_url" {
  description = "Pilot Web endpoint."
  value       = "https://${azurerm_container_app.web.latest_revision_fqdn}"
}

output "core_internal_url" {
  description = "Internal Core API endpoint."
  value       = "https://${azurerm_container_app.core.latest_revision_fqdn}"
}

output "postgresql_fqdn" {
  description = "Private PostgreSQL endpoint."
  value       = azurerm_postgresql_flexible_server.pilot.fqdn
}

output "evidence_storage_account_name" {
  description = "Canonical evidence-byte storage account."
  value       = azurerm_storage_account.evidence.name
}

output "expires_at" {
  description = "Mandatory teardown deadline carried by the P0 resource tags."
  value       = var.expires_at
}
