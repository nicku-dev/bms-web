from odoo import models, fields, api

class BMSDuckDBPreviewWizard(models.TransientModel):
    _name = 'bms.duckdb.preview.wizard'
    _description = 'BMS DuckDB Report Preview'

    name = fields.Char(default='Preview Report via DuckDB')
    iframe_html = fields.Html(readonly=True, sanitize=False)

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}
