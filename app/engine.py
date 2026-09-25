import duckdb
import pandas as pd
from typing import Optional
from app.config import settings

class ReportEngine:
    def __init__(self, db_name: Optional[str] = None):
        self.conn = duckdb.connect(database=':memory:')
        self._init_postgres(db_name)

    def _init_postgres(self, db_name: Optional[str] = None):
        """Initializes the PostgreSQL extension and attaches to the target database."""
        self.conn.execute("INSTALL postgres;")
        self.conn.execute("LOAD postgres;")
        
        pg_url = settings.get_postgres_connection_string(db_name)
        self.conn.execute(f"ATTACH '{pg_url}' AS pg (TYPE postgres, READ_ONLY);")

    def get_all_tags(self) -> list[str]:
        """Fetches all unique account tags from the database."""
        query = "SELECT DISTINCT name->>'en_US' as tag_name FROM account_account_tag WHERE name->>'en_US' IS NOT NULL ORDER BY tag_name"
        duckdb_query = f"SELECT * FROM postgres_query('pg', $${query}$$)"
        try:
            df = self.conn.execute(duckdb_query).df()
            return df['tag_name'].tolist()
        except Exception as e:
            print(f"Error fetching tags: {e}")
            return []

    def get_all_vessels(self) -> list[dict]:
        """Fetches all fleet combinations (vessels)."""
        query = "SELECT id, name, is_third_party FROM fleet_combination ORDER BY name"
        duckdb_query = f"SELECT * FROM postgres_query('pg', $${query}$$)"
        try:
            df = self.conn.execute(duckdb_query).df()
            return df.to_dict('records')
        except Exception as e:
            print(f"Error fetching vessels: {e}")
            return []

    def get_all_quarters_by_tag(
        self, 
        year: int,
        tag_name: str, 
        report_type: str = 'fps'
    ) -> pd.DataFrame:
        """
        Extracts the financial metric (sum of -balance) for a specific account, 
        grouped by vessel and quarter.
        report_type can be 'fps', 'non_fps', or 'ho'.
        """
        if report_type == 'ho':
            query = f"""
                SELECT 
                    'Head Office' AS vessel_name,
                    EXTRACT(QUARTER FROM aml.date)::int AS quarter,
                    sum(-aml.balance * (jad.value::numeric / 100.0)) AS value
                FROM account_move_line aml
                JOIN LATERAL jsonb_each_text(aml.analytic_distribution) jad(key, value) ON TRUE
                JOIN LATERAL regexp_split_to_table(jad.key, ',') as split_key ON TRUE
                JOIN account_analytic_account aaa ON aaa.id = split_key::int
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN account_account_account_tag aat_rel ON aa.id = aat_rel.account_account_id
                JOIN account_account_tag aat ON aat.id = aat_rel.account_account_tag_id
                WHERE aml.parent_state = 'posted'
                  AND (aat.name->>'en_US' = '{tag_name}' OR aat.name->>'id_ID' = '{tag_name}' OR aat.name::text LIKE '%{tag_name}%')
                  AND EXTRACT(YEAR FROM aml.date) = {year}
                  AND (aaa.name->>'en_US' = 'Head Office' OR aaa.name->>'id_ID' = 'Head Office')
                GROUP BY EXTRACT(QUARTER FROM aml.date)
            """
        else:
            query = f"""
                SELECT 
                    fc.name AS vessel_name,
                    EXTRACT(QUARTER FROM aml.date)::int AS quarter,
                    sum(-aml.balance * (jad.value::numeric / 100.0)) AS value
                FROM account_move_line aml
                JOIN LATERAL jsonb_each_text(aml.analytic_distribution) jad(key, value) ON TRUE
                JOIN LATERAL regexp_split_to_table(jad.key, ',') as split_key ON TRUE
                JOIN account_analytic_account aaa ON aaa.id = split_key::int
                JOIN fleet_combination fc ON fc.analytic_account_id = aaa.id
                JOIN account_account aa ON aa.id = aml.account_id
                JOIN account_account_account_tag aat_rel ON aa.id = aat_rel.account_account_id
                JOIN account_account_tag aat ON aat.id = aat_rel.account_account_tag_id
                WHERE aml.parent_state = 'posted'
                  AND (aat.name->>'en_US' = '{tag_name}' OR aat.name->>'id_ID' = '{tag_name}' OR aat.name::text LIKE '%{tag_name}%')
                  AND EXTRACT(YEAR FROM aml.date) = {year}
                GROUP BY fc.name, EXTRACT(QUARTER FROM aml.date)
            """
        duckdb_query = f"SELECT * FROM postgres_query('pg', '{query.replace(chr(39), chr(39)*2)}')"
        return self.conn.execute(duckdb_query).df()

    def get_kpi_trip(self, year: int, report_type: str = 'fps') -> pd.DataFrame:
        if report_type == 'ho':
            return pd.DataFrame(columns=['vessel_name', 'quarter', 'value'])
            
        query = f"""
            SELECT vessel_name, quarter, SUM(trip_count) AS value
            FROM (
                SELECT 
                    fc.name AS vessel_name,
                    EXTRACT(QUARTER FROM am.invoice_date)::int AS quarter,
                    count(DISTINCT so.fo_number_id) AS trip_count
                FROM account_move am
                JOIN account_move_line aml ON am.id = aml.move_id
                JOIN sale_order_line_invoice_rel sil ON sil.invoice_line_id = aml.id
                JOIN sale_order_line sol ON sil.order_line_id = sol.id
                JOIN sale_order so ON so.id = sol.order_id
                JOIN fleet_combination fc ON fc.id = so.nama_kapal_id
                WHERE am.state = 'posted'
                  AND EXTRACT(YEAR FROM am.invoice_date) = {year}
                GROUP BY am.id, so.name, fc.name, EXTRACT(QUARTER FROM am.invoice_date)
            ) sub
            GROUP BY vessel_name, quarter
        """
        duckdb_query = f"SELECT * FROM postgres_query('pg', '{query.replace(chr(39), chr(39)*2)}')"
        return self.conn.execute(duckdb_query).df()

    def get_kpi_kapasitas(self, year: int, report_type: str = 'fps') -> pd.DataFrame:
        if report_type == 'ho':
            return pd.DataFrame(columns=['vessel_name', 'quarter', 'value'])
            
        query = f"""
            SELECT 
                fc.name AS vessel_name,
                q.quarter,
                COALESCE(NULLIF(fvm3.cargo_capacity::numeric, 0), NULLIF(fvm.cargo_capacity::numeric, 0), 0) AS value
            FROM fleet_combination fc
            CROSS JOIN (VALUES (1), (2), (3), (4)) AS q(quarter)
            JOIN account_analytic_account aaa ON aaa.id = fc.analytic_account_id
            JOIN fleet_vehicle fv ON fc.primary_ship = fv.id
            JOIN fleet_vehicle_model fvm ON fv.model_id = fvm.id
            LEFT JOIN fleet_vehicle fv3 ON fc.secondary_ship = fv3.id
            LEFT JOIN fleet_vehicle_model fvm3 ON fv3.model_id = fvm3.id
        """
        duckdb_query = f"SELECT * FROM postgres_query('pg', '{query.replace(chr(39), chr(39)*2)}')"
        return self.conn.execute(duckdb_query).df()

    def close(self):
        """Closes the DuckDB connection."""
        self.conn.close()
