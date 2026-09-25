# Adopt the existing Azure Service Health alert into the authoritative P0 state.
# Safe to keep after the first successful apply; subsequent plans treat it as already imported.
import {
  to = azurerm_monitor_activity_log_alert.service_health
  id = "/subscriptions/${var.subscription_id}/resourceGroups/rg-soaiacore-p0-34utxi/providers/Microsoft.Insights/activityLogAlerts/alrt-soaiacore-p0-servicehealth"
}
