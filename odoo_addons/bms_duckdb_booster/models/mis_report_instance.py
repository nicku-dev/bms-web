import requests
from odoo import models, fields, exceptions, _

class MisReportInstance(models.Model):
    _inherit = 'mis.report.instance'

    duckdb_boost_enabled = fields.Boolean(
        string="DuckDB Boost Engine",
        default=True,
        help="If checked, matrix computation will be delegated to DuckDB (BMS-Web) for 1000x faster execution."
    )

    def action_compute_via_duckdb(self):
        """
        Preview using DuckDB. We ensure the flag is enabled.
        """
        self.ensure_one()
        self.duckdb_boost_enabled = True
        return self.preview()

    def compute(self):
        """
        Override the core MIS Builder compute method.
        Instead of running slow PostgreSQL queries and Python math,
        we fetch the pre-compiled JSON dictionary from DuckDB (BMS-Web).
        """
        self.ensure_one()
        if not self.duckdb_boost_enabled:
            return super().compute()

        # Hack: To get the skeleton matrix without running slow PostgreSQL queries,
        # we temporarily change all period dates to '1970-01-01' where no data exists.
        old_dates = {}
        # Avoid constraint errors by writing all at once, or bypassing check
        # Actually mis.report.instance.period doesn't have strict constraints on 1970 usually
        for period in self.period_ids:
            old_dates[period.id] = {
                'date_from': period.date_from,
                'date_to': period.date_to,
            }
            # We use sudo/write to bypass some UI constraints if any
            period.sudo().write({
                'date_from': '1970-01-01',
                'date_to': '1970-01-01',
            })
            
        try:
            # This is now lightning fast because Postgres finds 0 move lines!
            skeleton_matrix = super().compute()
        finally:
            # Revert the dates back immediately
            for period in self.period_ids:
                period.sudo().write(old_dates[period.id])

        # Hardcoded for now. Can be moved to ir.config_parameter
        bms_web_url = self.env['ir.config_parameter'].sudo().get_param('bms_duckdb.url', 'http://10.100.1.58:3000')
        api_endpoint = f"{bms_web_url}/api/odoo/compute_booster_direct"
        
        payload = {
            "skeleton_json": skeleton_matrix,
            "target_db_name": self.env.cr.dbname,
            "report_name": self.name,
        }
        
        import requests
        try:
            response = requests.post(api_endpoint, json=payload, timeout=30)
            if response.status_code == 200:
                result_data = response.json()
                # Inject notes if any (following standard Odoo behavior)
                result_data["notes"] = self.get_notes_by_cell_id()
                return result_data
            else:
                error_msg = response.json().get('detail', 'Unknown error')
                raise exceptions.UserError(_("DuckDB Native Compilation failed: %s") % error_msg)
                
        except requests.exceptions.RequestException as e:
            raise exceptions.UserError(_("Failed to connect to BMS-Web DuckDB Engine: \n%s") % str(e))
