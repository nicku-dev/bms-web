{
    'name': 'BMS DuckDB Booster',
    'version': '18.0.1.0.0',
    'summary': 'Mencegah Odoo Timeout dengan mendelegasikan komputasi laporan berat (MIS Builder) ke DuckDB (FastAPI).',
    'description': """
BMS DuckDB Booster
==================
Modul ini menghubungkan Odoo 18 dengan backend bms-web (FastAPI + DuckDB) untuk
mendelegasikan komputasi matriks yang sangat berat sehingga menghindari OOM dan Timeout pada server Odoo.
    """,
    'author': 'Lentera Teknologi',
    'depends': ['mis_builder', 'base'],
    'data': [
        'views/mis_report_instance_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
