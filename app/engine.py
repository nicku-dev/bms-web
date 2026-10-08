import duckdb
import pandas as pd
from typing import Optional
from app.config import settings

class ReportEngine:
    def __init__(self, db_name: Optional[str] = None, pg_kwargs: dict = None):
        self.conn = duckdb.connect(database=':memory:')
        self._init_postgres(db_name, pg_kwargs or {})

    def _init_postgres(self, db_name: Optional[str] = None, pg_kwargs: dict = None):
        """Initializes the PostgreSQL extension and attaches to the target database."""
        self.conn.execute("INSTALL postgres;")
        self.conn.execute("LOAD postgres;")
        
        pg_url = settings.get_postgres_connection_string(
            override_db_name=db_name,
            override_host=pg_kwargs.get('db_host'),
            override_port=pg_kwargs.get('db_port'),
            override_user=pg_kwargs.get('db_user'),
            override_password=pg_kwargs.get('db_password'),
        )
        self.conn.execute(f"ATTACH '{pg_url}' AS pg (TYPE postgres, READ_ONLY);")

    @property
    def account_code_column(self):
        if not hasattr(self, '_account_code_column'):
            try:
                query = "SELECT column_name FROM information_schema.columns WHERE table_name='account_account' AND column_name='code_store'"
                duckdb_query = f"SELECT * FROM postgres_query('pg', $${query}$$)"
                df = self.conn.execute(duckdb_query).df()
                if not df.empty:
                    self._account_code_column = 'code_store'
                else:
                    self._account_code_column = 'code'
            except Exception as e:
                print("Error checking account code column:", e)
                self._account_code_column = 'code'
        return self._account_code_column

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
        report_type: str = 'fps',
        account_code: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Extracts the financial metric (sum of -balance) for a specific account or tag, 
        grouped by vessel and quarter.
        """
        tag_filter = ""
        join_tags = ""
        if tag_name:
            tag_filter = f"AND (aat.name->>'en_US' = '{tag_name}' OR aat.name->>'id_ID' = '{tag_name}' OR aat.name::text LIKE '%{tag_name}%')"
            join_tags = """
                JOIN account_account_account_tag aat_rel ON aa.id = aat_rel.account_account_id
                JOIN account_account_tag aat ON aat.id = aat_rel.account_account_tag_id
            """
            
        acc_filter = ""
        if account_code:
            if self.account_code_column == 'code_store':
                acc_filter = f"AND aa.code_store::text LIKE '%\"{account_code}%'"
            else:
                acc_filter = f"AND aa.code LIKE '{account_code}%'"
            
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
                {join_tags}
                WHERE aml.parent_state = 'posted'
                  {tag_filter}
                  {acc_filter}
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
                {join_tags}
                WHERE aml.parent_state = 'posted'
                  {tag_filter}
                  {acc_filter}
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
                    EXTRACT(QUARTER FROM fo_inv.min_invoice_date)::int AS quarter,
                    count(DISTINCT so.fo_number_id) AS trip_count
                FROM sale_order so
                JOIN (
                    SELECT sol.order_id, min(am.invoice_date) AS min_invoice_date
                    FROM account_move am
                    JOIN account_move_line aml ON am.id = aml.move_id
                    JOIN sale_order_line_invoice_rel sil ON sil.invoice_line_id = aml.id
                    JOIN sale_order_line sol ON sil.order_line_id = sol.id
                    WHERE am.state = 'posted' AND am.invoice_date IS NOT NULL
                    GROUP BY sol.order_id
                ) fo_inv ON fo_inv.order_id = so.id
                JOIN fleet_combination fc ON fc.id = so.nama_kapal_id
                WHERE so.fo_number_id IS NOT NULL
                  AND EXTRACT(YEAR FROM fo_inv.min_invoice_date) = {year}
                GROUP BY fc.name, EXTRACT(QUARTER FROM fo_inv.min_invoice_date)
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

    def get_kpi_tpj_semua(self, year: int) -> pd.DataFrame:
        query = f"""
            SELECT EXTRACT(QUARTER FROM aml.date)::int AS quarter, sum(-aml.balance * (jad.value::numeric / 100.0)) AS value
            FROM account_move_line aml
            JOIN LATERAL jsonb_each_text(aml.analytic_distribution) jad(key, value) ON TRUE
            JOIN LATERAL regexp_split_to_table(jad.key, ',') as split_key ON TRUE
            JOIN account_analytic_account aaa ON aaa.id = split_key::int
            JOIN fleet_combination fc ON aaa.id = fc.analytic_account_id
            JOIN account_account aa ON aa.id = aml.account_id
            JOIN account_account_account_tag aat_rel ON aa.id = aat_rel.account_account_id
            JOIN account_account_tag aat ON aat.id = aat_rel.account_account_tag_id
            WHERE aml.parent_state = 'posted'
              AND fc.is_third_party = false
              AND (aat.name->>'en_US' = 'TW_PENDAPATAN JASA' OR aat.name::text LIKE '%TW_PENDAPATAN JASA%')
              AND EXTRACT(YEAR FROM aml.date) = {year}
            GROUP BY EXTRACT(QUARTER FROM aml.date)
        """
        duckdb_query = f"SELECT * FROM postgres_query('pg', '{query.replace(chr(39), chr(39)*2)}')"
        try:
            return self.conn.execute(duckdb_query).df()
        except Exception as e:
            print("Error get_kpi_tpj_semua:", e)
            return pd.DataFrame(columns=['quarter', 'value'])

    def get_mis_report_queries(self, report_id: int) -> dict:
        """
        Dynamically fetches the queries defined in the MIS Report template in Odoo.
        Returns a nested dict: { query_name: { field_name: value } }
        """
        if not report_id:
            return {}
            
        query = f"""
            SELECT 
                q.name AS query_name, 
                REPLACE(m.model, '.', '_') AS sql_view,
                f.name AS field_name,
                q.aggregate
            FROM mis_report_query q
            JOIN ir_model m ON q.model_id = m.id
            JOIN ir_model_fields_mis_report_query_rel rel ON rel.mis_report_query_id = q.id
            JOIN ir_model_fields f ON f.id = rel.ir_model_fields_id
            WHERE q.report_id = {report_id}
              AND (q.domain IS NULL OR q.domain = '' OR q.domain = '[]')
        """
        escaped_query = query.replace("'", "''")
        duckdb_query = f"SELECT * FROM postgres_query('pg', '{escaped_query}')"
        try:
            df = self.conn.execute(duckdb_query).df()
        except Exception as e:
            print(f"Error fetching mis_report_query metadata for report {report_id}: {e}")
            return {}
            
        queries = {}
        for _, row in df.iterrows():
            q_name = row['query_name']
            if q_name not in queries:
                queries[q_name] = {
                    'view': row['sql_view'],
                    'fields': []
                }
            queries[q_name]['fields'].append({
                'name': row['field_name'],
                'agg': row['aggregate']
            })
            
        results = {}
        for q_name, q_info in queries.items():
            view = q_info['view']
            fields = q_info['fields']
            selects = []
            for f in fields:
                agg = str(f['agg']).upper() if f['agg'] else 'SUM'
                if agg == 'NONE' or agg == 'NAN':
                    agg = 'SUM'
                selects.append(f"{agg}({f['name']}) as {f['name']}")
                
            select_str = ", ".join(selects)
            
            try:
                custom_tags = {
                    'tpbb': 'TW_Pendapatan bunga bank',
                    'tpll': 'TW_Pendapatan lain-lain',
                    'tlsk': 'TW_Laba selisih Kurs',
                    'tbll': 'TW_Biaya Lain-lain',
                    'tbab': 'TW_Biaya Admin Bank',
                    'trsk': 'TW_Rugi selisih Kurs',
                    'tbpll': 'TW_Beban Pajak Lain-lain'
                }
                
                if q_name in custom_tags:
                    tag_name = custom_tags[q_name]
                    fetch_sql = f"""
                        WITH custom_view AS (
                            SELECT 
                                1 as id,
                                '2026-12-31'::date as date,
                                '{tag_name}' as keterangan,
                                COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 1 THEN aml.balance ELSE 0 END), 0) as sumq1_25,
                                COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 2 THEN aml.balance ELSE 0 END), 0) as sumq2_25,
                                COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 3 THEN aml.balance ELSE 0 END), 0) as sumq3_25,
                                COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 4 THEN aml.balance ELSE 0 END), 0) as sumq4_25,
                                COALESCE(SUM(aml.balance), 0) as ytd_25
                            FROM pg.account_move_line aml
                            JOIN pg.account_account_account_tag aaat ON aaat.account_account_id = aml.account_id 
                            JOIN pg.account_account_tag aat ON aat.id = aaat.account_account_tag_id 
                            WHERE aat.name->>'en_US' = '{tag_name}' 
                              AND aml.parent_state = 'posted'
                        )
                        SELECT {select_str} FROM custom_view
                    """
                else:
                    fetch_sql = f"SELECT {select_str} FROM pg.{view}"
                data = self.conn.execute(fetch_sql).fetchone()
                
                results[q_name] = {}
                for i, f in enumerate(fields):
                    val = data[i] if data else 0.0
                    try:
                        results[q_name][f['name']] = float(val or 0)
                    except:
                        results[q_name][f['name']] = 0.0
            except Exception as e:
                print(f"Error fetching query {q_name} from {view}: {e}")
                
        return results


    def get_audit_trail(
        self, 
        year: int,
        quarter: int,
        vessel_name: str,
        tag_name: Optional[str] = None, 
        account_code: Optional[str] = None
    ) -> list[dict]:
        """
        Fetches detailed journal items for a specific vessel, quarter, and account/tag.
        """
        if tag_name == 'undefined' or tag_name == 'null':
            tag_name = None
        if account_code == 'undefined' or account_code == 'null':
            account_code = None
            
        if vessel_name:
            vessel_name = vessel_name.replace('Kapal - ', '').strip()
            
        tag_filter = ""
        join_tags = ""
        if tag_name:
            tag_filter = f"AND (aat.name->>'en_US' = '{tag_name}' OR aat.name->>'id_ID' = '{tag_name}' OR aat.name::text LIKE '%{tag_name}%')"
            join_tags = """
                JOIN account_account_account_tag aat_rel ON aa.id = aat_rel.account_account_id
                JOIN account_account_tag aat ON aat.id = aat_rel.account_account_tag_id
            """
            
        acc_filter = ""
        if account_code:
            if self.account_code_column == 'code_store':
                acc_filter = f"AND aa.code_store::text LIKE '%\"{account_code}%'"
            else:
                acc_filter = f"AND aa.code LIKE '{account_code}%'"
            
        vessel_filter = ""
        if vessel_name and vessel_name != 'Head Office':
            vessel_filter = f"AND fc.name = '{vessel_name}'"
            
        quarter_filter = ""
        if quarter and quarter != 'ytd':
            # quarter is e.g. 'q1' or 'Q1'
            q_num = str(quarter).lower().replace('q', '')
            if q_num in ['1', '2', '3', '4']:
                quarter_filter = f"AND EXTRACT(QUARTER FROM aml.date) = {q_num}"
            
        if self.account_code_column == 'code_store':
            col_select = "(SELECT value FROM jsonb_each_text(aa.code_store) LIMIT 1) as account_code,"
        else:
            col_select = "aa.code as account_code,"
            
        if vessel_name == 'Head Office':
            query = f"""
                SELECT 
                    am.name as move_name,
                    aml.date::text as date,
                    aml.name as label,
                    aml.ref as ref,
                    {col_select}
                    aa.name->>'en_US' as account_name,
                    rp.name as partner_name,
                    aml.debit as debit,
                    aml.credit as credit,
                    (-aml.balance * (jad.value::numeric / 100.0)) as value
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                LEFT JOIN res_partner rp ON rp.id = aml.partner_id
                JOIN LATERAL jsonb_each_text(aml.analytic_distribution) jad(key, value) ON TRUE
                JOIN LATERAL regexp_split_to_table(jad.key, ',') as split_key ON TRUE
                JOIN account_analytic_account aaa ON aaa.id = split_key::int
                JOIN account_account aa ON aa.id = aml.account_id
                {join_tags}
                WHERE aml.parent_state = 'posted'
                  {tag_filter}
                  {acc_filter}
                  AND EXTRACT(YEAR FROM aml.date) = {year}
                  {quarter_filter}
                  AND (aaa.name->>'en_US' = 'Head Office' OR aaa.name->>'id_ID' = 'Head Office')
                ORDER BY aml.date DESC
                LIMIT 500
            """
        else:
            query = f"""
                SELECT 
                    am.name as move_name,
                    aml.date::text as date,
                    aml.name as label,
                    aml.ref as ref,
                    {col_select}
                    aa.name->>'en_US' as account_name,
                    rp.name as partner_name,
                    aml.debit as debit,
                    aml.credit as credit,
                    (-aml.balance * (jad.value::numeric / 100.0)) as value
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                LEFT JOIN res_partner rp ON rp.id = aml.partner_id
                JOIN LATERAL jsonb_each_text(aml.analytic_distribution) jad(key, value) ON TRUE
                JOIN LATERAL regexp_split_to_table(jad.key, ',') as split_key ON TRUE
                JOIN account_analytic_account aaa ON aaa.id = split_key::int
                JOIN fleet_combination fc ON fc.analytic_account_id = aaa.id
                JOIN account_account aa ON aa.id = aml.account_id
                {join_tags}
                WHERE aml.parent_state = 'posted'
                  {tag_filter}
                  {acc_filter}
                  AND EXTRACT(YEAR FROM aml.date) = {year}
                  {quarter_filter}
                  {vessel_filter}
                ORDER BY aml.date DESC
                LIMIT 500
            """
            
        duckdb_query = f"SELECT * FROM postgres_query('pg', '{query.replace(chr(39), chr(39)*2)}')"
        try:
            df = self.conn.execute(duckdb_query).df()
            return df.to_dict('records')
        except Exception as e:
            print(f"Error fetching audit trail: {e}")
            return []

    def close(self):
        """Closes the DuckDB connection."""
        self.conn.close()
