#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import duckdb
from app.config import settings
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_rows', 100)

def get_duckdb_conn(db_name=None):
    conn = duckdb.connect(database=':memory:')
    conn.execute("INSTALL postgres;")
    conn.execute("LOAD postgres;")
    pg_url = settings.get_postgres_connection_string(db_name)
    print(f"🔌 Connected DuckDB to PostgreSQL ({settings.db_host}:{settings.db_port}/{db_name or settings.db_name})")
    conn.execute(f"ATTACH '{pg_url}' AS pg (TYPE postgres, READ_ONLY);")
    return conn

def main():
    conn = get_duckdb_conn()
    
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print(f"\n🔍 Executing query:\n{query}\n" + "-"*50)
        try:
            df = conn.execute(query).df()
            print(df)
            print(f"\nTotal rows: {len(df)}")
        except Exception as e:
            print(f"❌ Error executing query: {e}")
        return

    print("\n💡 DuckDB Interactive REPL attached to PostgreSQL schema 'pg'.")
    print("Contoh Query:")
    print("  - SHOW TABLES FROM pg;")
    print("  - SELECT count(*) FROM pg.account_move;")
    print("  - SELECT * FROM pg.fleet_combination LIMIT 5;")
    print("  - exit / quit untuk keluar.\n")

    while True:
        try:
            query = input("duckdb> ").strip()
            if not query:
                continue
            if query.lower() in ('exit', 'quit', '\\q'):
                break
            
            # Auto prefix if user typed simple SELECT without schema if needed, or execute directly
            df = conn.execute(query).df()
            print(df)
            print(f"\n[Rows: {len(df)}]")
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
