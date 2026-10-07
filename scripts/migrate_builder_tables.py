import sqlite3
import os
import sys

def migrate():
    # Use the absolute path to ensure we hit the correct db
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'app_config.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Creating bms_reports table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bms_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT
    )
    """)
    
    print("Creating bms_report_rows table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bms_report_rows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_id INTEGER NOT NULL,
        sequence INTEGER DEFAULT 10,
        parent_id INTEGER,
        label TEXT NOT NULL,
        variable_name TEXT,
        row_type TEXT DEFAULT 'tag_query', -- 'header', 'tag_query', 'formula'
        tag_name TEXT,
        formula TEXT,
        is_expense BOOLEAN DEFAULT 0,
        is_percentage BOOLEAN DEFAULT 0,
        FOREIGN KEY(report_id) REFERENCES bms_reports(id),
        FOREIGN KEY(parent_id) REFERENCES bms_report_rows(id)
    )
    """)
    
    conn.commit()
    conn.close()
    print("Migration successful.")

if __name__ == '__main__':
    migrate()
