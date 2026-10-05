import duckdb
from app.config import settings

def main():
    conn = duckdb.connect(':memory:')
    conn.execute("INSTALL postgres; LOAD postgres;")
    pg_url = settings.get_postgres_connection_string("MASTER_PROD_2_1")
    conn.execute(f"ATTACH '{pg_url}' AS pg (TYPE postgres, READ_ONLY);")
    
    query = """
        SELECT fc.name AS vessel_name, sum(-aml.balance * (jad.value::numeric / 100.0)) AS value
        FROM account_move_line aml
        JOIN LATERAL jsonb_each_text(aml.analytic_distribution) jad(key, value) ON TRUE
        JOIN LATERAL regexp_split_to_table(jad.key, ',') as split_key ON TRUE
        JOIN account_analytic_account aaa ON aaa.id = split_key::int
        JOIN fleet_combination fc ON aaa.id = fc.analytic_account_id
        JOIN account_account aa ON aa.id = aml.account_id
        JOIN account_account_account_tag aat_rel ON aa.id = aat_rel.account_account_id
        JOIN account_account_tag aat ON aat.id = aat_rel.account_account_tag_id
        WHERE aml.parent_state = 'posted'
          AND (aat.name->>'en_US' = 'TW_PENDAPATAN JASA' OR aat.name::text LIKE '%TW_PENDAPATAN JASA%')
          AND EXTRACT(YEAR FROM aml.date) = 2026
          AND EXTRACT(QUARTER FROM aml.date) = 3
        GROUP BY fc.name
        ORDER BY fc.name
    """
    duckdb_query = f"SELECT * FROM postgres_query('pg', '{query.replace(chr(39), chr(39)*2)}')"
    
    df = conn.execute(duckdb_query).df()
    
    print("TOTAL PENDAPATAN JASA Q3 (SQL):")
    total = 0.0
    for _, row in df.iterrows():
        v = row['vessel_name']
        val = row['value']
        if val != 0:
            print(f"- {v}: {val:,.2f}")
            total += val
            
    print(f"---")
    print(f"TOTAL PENJUMLAHAN: {total:,.2f}")

if __name__ == '__main__': main()
