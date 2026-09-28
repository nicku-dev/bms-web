## Server Management
- Server 'dev' IP is 10.100.1.58. The hostname on the server is fr-100-091.
- The user nicku.pasaribu uses passwordless SSH to login.

## Environment Architecture
There are two instances managed in this project on the same server (10.100.1.58):

1. **SIT4 (System Integration Testing)**
   - Branch: `sit`
   - Source Code Folder: `~/srv/odoo-sit4/bms-web`
   - Port: `8501`
   - Service: `odoo-sit4.service`

2. **DEV4 (Development)**
   - Branch: `dev`
   - Source Code Folder: `~/srv/odoo-dev4/bms-web`
   - Port: `3000`
   - Service: `odoo-dev4.service`

## BMS Web Service Standards
- **Naming Convention:** All services must follow the naming format `odoo-*.service` (e.g., `odoo-sit4.service`, `odoo-dev4.service`). Do NOT use `bms-web-*.service`.
- **Placement:** Services must be placed in the system-wide folder `/etc/systemd/system/`.
- **Commands:** Use `sudo systemctl ...` to manage them.
