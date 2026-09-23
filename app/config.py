import os
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path
env_path = Path(__file__).parent.parent.parent / '.env'

class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str
    db_password: str = ""
    db_name: str
    app_config_db_url: str = ""  # Akan dibaca dari APP_CONFIG_DB_URL di .env
    odoo_url: str = "http://localhost:8069" # Default fallback
    odoo_password: str = "" # Password untuk akun admin XML-RPC

    model_config = SettingsConfigDict(
        env_file=str(env_path), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    @property
    def postgres_connection_string(self) -> str:
        """Returns the PostgreSQL connection string suitable for DuckDB's ATTACH command or psycopg."""
        pwd_part = f":{self.db_password}" if self.db_password else ""
        return f"postgresql://{self.db_user}{pwd_part}@{self.db_host}:{self.db_port}/{self.db_name}"
        
    def get_postgres_connection_string(self, override_db_name: str = None) -> str:
        """Returns the PostgreSQL connection string with an optional database override."""
        pwd_part = f":{self.db_password}" if self.db_password else ""
        target_db = override_db_name if override_db_name else self.db_name
        return f"postgresql://{self.db_user}{pwd_part}@{self.db_host}:{self.db_port}/{target_db}"

settings = Settings()
