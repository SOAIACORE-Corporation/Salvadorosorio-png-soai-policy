resource "azurerm_user_assigned_identity" "workload" {
  name                = "id-${local.name_prefix}-workload-${random_string.suffix.result}"
  location            = azurerm_resource_group.pilot.location
  resource_group_name = azurerm_resource_group.pilot.name
  tags                = local.required_tags
}

resource "azurerm_user_assigned_identity" "deployer" {
  name                = "id-${local.name_prefix}-deployer-${random_string.suffix.result}"
  location            = azurerm_resource_group.pilot.location
  resource_group_name = azurerm_resource_group.pilot.name
  tags                = local.required_tags
}

resource "azurerm_federated_identity_credential" "github_branch" {
  name                      = "github-${replace(var.github_branch, "/", "-")}"
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = "https://token.actions.githubusercontent.com"
  subject                   = "repo:${var.github_repository}:ref:refs/heads/${var.github_branch}"
  user_assigned_identity_id = azurerm_user_assigned_identity.deployer.id
}

resource "azurerm_role_assignment" "deployer_contributor" {
  scope                = azurerm_resource_group.pilot.id
  role_definition_name = "Contributor"
  principal_id         = azurerm_user_assigned_identity.deployer.principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "deployer_rbac" {
  scope                = azurerm_resource_group.pilot.id
  role_definition_name = "Role Based Access Control Administrator"
  principal_id         = azurerm_user_assigned_identity.deployer.principal_id
  principal_type       = "ServicePrincipal"
}
