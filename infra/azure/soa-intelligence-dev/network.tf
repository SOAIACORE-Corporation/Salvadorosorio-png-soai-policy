resource "azurerm_virtual_network" "soa_intelligence" {
  name                = "vnet-${local.name_prefix}"
  address_space       = ["10.60.0.0/16"]
  location            = azurerm_resource_group.soa_intelligence.location
  resource_group_name = azurerm_resource_group.soa_intelligence.name
  tags                = local.required_tags
}

resource "azurerm_subnet" "postgresql" {
  name                 = "snet-postgresql"
  resource_group_name  = azurerm_resource_group.soa_intelligence.name
  virtual_network_name = azurerm_virtual_network.soa_intelligence.name
  address_prefixes     = ["10.60.10.0/24"]

  delegation {
    name = "postgresql-flexible-server"

    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_private_dns_zone" "postgresql" {
  name                = "${local.name_prefix}.postgres.database.azure.com"
  resource_group_name = azurerm_resource_group.soa_intelligence.name
  tags                = local.required_tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "link-${local.name_prefix}-postgresql"
  resource_group_name   = azurerm_resource_group.soa_intelligence.name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = azurerm_virtual_network.soa_intelligence.id
  registration_enabled  = false
  tags                  = local.required_tags
}
