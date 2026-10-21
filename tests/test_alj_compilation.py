import unittest
from app.db import SessionLocal
from app.models import Company
from app.builder import get_vessels, get_tags, get_accounts, preview_template, PreviewRequest

class TestALJCompilation(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.company = self.db.query(Company).filter(Company.id == 3).first()

    def tearDown(self):
        self.db.close()

    def test_alj_company_loaded(self):
        self.assertIsNotNone(self.company, "Company ALJ (id=3) should exist")
        self.assertEqual(self.company.target_db_name, "ALJ_ODOO_18_PROD")
        pg_kwargs = self.company.get_pg_kwargs()
        self.assertIsNotNone(pg_kwargs)
        self.assertEqual(pg_kwargs.get("db_host"), "10.110.1.7")

    def test_alj_vessels(self):
        vessels = get_vessels(3, self.db)
        self.assertGreaterEqual(len(vessels), 8, "ALJ should have at least 8 fleet combinations")
        names = [v.get("name") for v in vessels]
        self.assertTrue(any("AS JAYA 2" in n for n in names))
        self.assertTrue(any("ARUNG LAUTAN 5001" in n.upper() for n in names))

    def test_alj_tags(self):
        tags = get_tags(3, self.db)
        self.assertGreater(len(tags), 50, "ALJ should have >50 account tags")
        self.assertIn("BEBAN POKOK PENDAPATAN JASA", tags)

    def test_alj_preview_numbers_not_empty(self):
        payload = PreviewRequest(
            company_id=3,
            year="2026",
            vessels=[
                {"id": 5, "name": "TB. AS JAYA 2 / BG. AS GLORY 11"},
                {"id": 6, "name": "TB. AS JAYA 6 / BG. AS GLORY 16"}
            ],
            rows=[
                {"type": "data", "code": "rev", "label": "PENDAPATAN JASA", "expression": "TW_PENDAPATAN JASA"},
                {"type": "data", "code": "cogs", "label": "BEBAN POKOK PENDAPATAN JASA", "expression": "BEBAN POKOK PENDAPATAN JASA"},
                {"type": "formula", "code": "gross_profit", "label": "LABA KOTOR", "expression": "rev - cogs"}
            ]
        )
        res = preview_template(payload, self.db)
        self.assertEqual(res.get("status"), "success")
        self.assertIsNone(res.get("warning"))
        
        matrix = res.get("data", {})
        body = matrix.get("body", [])
        self.assertEqual(len(body), 3)

        rev_row = body[0]
        cogs_row = body[1]
        gp_row = body[2]

        rev_vals = [c.get("val_r") for c in rev_row.get("cells", [])]
        # At least some quarters should have non-dash values
        non_empty_rev = [v for v in rev_vals if v != "-"]
        self.assertGreater(len(non_empty_rev), 0, "Revenue should not be all empty '-'")
        self.assertTrue(any("9,791,635,405" in v for v in non_empty_rev), "Expected Q3 revenue ~9.79B IDR")

        cogs_vals = [c.get("val_r") for c in cogs_row.get("cells", [])]
        non_empty_cogs = [v for v in cogs_vals if v != "-"]
        self.assertGreater(len(non_empty_cogs), 0, "COGS should not be all empty '-'")

        gp_vals = [c.get("val_r") for c in gp_row.get("cells", [])]
        non_empty_gp = [v for v in gp_vals if v != "-"]
        self.assertGreater(len(non_empty_gp), 0, "Gross profit formula should produce calculated numbers")

if __name__ == "__main__":
    unittest.main()
