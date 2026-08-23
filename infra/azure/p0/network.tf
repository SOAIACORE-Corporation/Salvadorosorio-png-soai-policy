resource "azurerm_resource_group" "pilot" {
  name     = "rg-${local.name_prefix}-${random_string.suffix.result}"
  location = var.location
  tags     = local.required_tags
}

resource "azurerm_virtual_network" "pilot" {
  name                = "vnet-${local.name_prefix}-${random_string.suffix.result}"
  location            = azurerm_resource_group.pilot.location
  resource_group_name = azurerm_resource_group.pilot.name
  address_space       = ["10.42.0.0/23"]
  tags                = local.required_tags
}

resource "azurerm_subnet" "container_apps" {
  name                 = "snet-container-apps"
  resource_group_name  = azurerm_resource_group.pilot.name
  virtual_network_name = azurerm_virtual_network.pilot.name
  address_prefixes     = ["10.42.0.0/27"]

  delegation {
    name = "container-apps-environment"

    service_delegation {
      name    = "Microsoft.App/environments"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_subnet" "postgresql" {
  name                 = "snet-postgresql"
  resource_group_name  = azurerm_resource_group.pilot.name
  virtual_network_name = azurerm_virtual_network.pilot.name
  address_prefixes     = ["10.42.1.0/28"]

  delegation {
    name = "postgresql-flexible-server"

    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_private_dns_zone" "postgresql" {
  name                = "${local.name_prefix}-${random_string.suffix.result}.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.pilot.name
  tags                = local.required_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                 = "link-${local.name_prefix}"
  private_dns_zone_id  = azurerm_private_dns_zone.postgresql.id
  virtual_network_id   = azurerm_virtual_network.pilot.id
  registration_enabled = false
  tags                 = local.required_tags
}
