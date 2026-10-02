import pandas as pd
from typing import Dict, Optional

class CompilerFetcher:
    def __init__(self, engine, year, report_type):
        self.engine = engine
        self.year = year
        self.report_type = report_type
        
        # Precompute common KPIs to memory to avoid multiple queries
        self.cache = {}
        
    def get_df_by_tag_and_account(self, tag: Optional[str], account_code: Optional[str]) -> pd.DataFrame:
        """Fetch general ledger data grouped by quarter and vessel, using cache."""
        cache_key = f"{tag}_{account_code}"
        if cache_key not in self.cache:
            df = self.engine.get_all_quarters_by_tag(self.year, tag, self.report_type, account_code)
            self.cache[cache_key] = df
        return self.cache[cache_key]

    def get_kpi_trip(self) -> pd.DataFrame:
        """Fetch TRIP KPI."""
        if 'kpi_trip' not in self.cache:
            self.cache['kpi_trip'] = self.engine.get_kpi_trip(self.year, self.report_type)
        return self.cache['kpi_trip']
        
    def get_kpi_kapasitas(self) -> pd.DataFrame:
        """Fetch KAPASITAS KPI."""
        if 'kpi_kapasitas' not in self.cache:
            self.cache['kpi_kapasitas'] = self.engine.get_kpi_kapasitas(self.year, self.report_type)
        return self.cache['kpi_kapasitas']
