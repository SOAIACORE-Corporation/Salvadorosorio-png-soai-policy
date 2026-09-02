output "resource_group_name" {
  description = "Resource group containing the protected Terraform state store."
  value       = azurerm_resource_group.state.name
}

output "storage_account_name" {
  description = "Storage Account used by the azurerm backend."
  value       = azurerm_storage_account.state.name
}

output "container_name" {
  description = "Private Blob container used by the azurerm backend."
  value       = azurerm_storage_container.state.name
}

output "controlled_pilot_state_key" {
  description = "Canonical backend key for the controlled pilot workload state."
  value       = "soaiacore/controlled-pilot/terraform.tfstate"
}
