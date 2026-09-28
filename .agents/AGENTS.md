
## BMS Web Service Standards
- **Naming Convention:** All services must follow the naming format `odoo-*.service` (e.g., `odoo-sit4.service`, `odoo-dev4.service`). Do NOT use `bms-web-*.service`.
- **Placement:** Services must be placed in the system-wide folder `/etc/systemd/system/`.
- **Commands:** Use `sudo systemctl ...` to manage them.
