import os
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path
env_path = Path(__file__).parent.parent / '.env'

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
        
    def get_postgres_connection_string(self, override_db_name: str = None, override_host: str = None, override_port: int = None, override_user: str = None, override_password: str = None) -> str:
        """Returns the PostgreSQL connection string with optional overrides."""
        host = override_host or self.db_host
        port = override_port or self.db_port
        user = override_user or self.db_user
        pwd = override_password if override_password is not None else self.db_password
        db_name = override_db_name or self.db_name
        
        pwd_part = f":{pwd}" if pwd else ""
        return f"postgresql://{user}{pwd_part}@{host}:{port}/{db_name}"
settings = Settings()
