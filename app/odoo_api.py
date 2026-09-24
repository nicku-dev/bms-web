import requests
import json
from typing import Dict, Any, List, Optional
from app.config import settings

class OdooAPI:
    def __init__(self, db_name: str, url: str = None, username: str = None, password: str = None):
        """
        Initialize JSON-RPC connection to Odoo.
        """
        self.url = url or settings.odoo_url
        self.db = db_name
        self.username = username or 'admin'
        self.password = password or settings.odoo_password
        self.session = requests.Session()
        self.session.verify = False  # Bypass SSL for internal
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        self.uid = self.authenticate()
        if not self.uid:
            raise ValueError(f"Failed to authenticate with Odoo (DB: {self.db}, User: {self.username})")

    def _call(self, service: str, method: str, *args):
        url = f"{self.url}/jsonrpc"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": service,
                "method": method,
                "args": args
            },
            "id": 1
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = self.session.post(url, data=json.dumps(payload), headers=headers, timeout=900)
            if response.status_code != 200:
                raise ConnectionError(f"Server Odoo merespon HTTP {response.status_code}")
            res = response.json()
            if 'error' in res:
                raise Exception(res['error'].get('message', res['error']))
            return res.get('result')
        except requests.exceptions.Timeout:
            raise ConnectionError(f"Koneksi ke server Odoo ({self.url}) Timeout (melewati batas 900 detik)")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Gagal terhubung ke server Odoo ({self.url}): {e}")

    def authenticate(self):
        url = f"{self.url}/web/session/authenticate"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.db,
                "login": self.username,
                "password": self.password
            },
            "id": 1
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = self.session.post(url, data=json.dumps(payload), headers=headers, timeout=900)
            if response.status_code != 200:
                return None
            res = response.json()
            if 'error' in res:
                return None
            return res.get('result', {}).get('uid')
        except Exception:
            return None

    def execute_kw(self, model: str, method: str, args: List, kwargs: Dict = None):
        url = f"{self.url}/web/dataset/call_kw"
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": args,
                "kwargs": kwargs or {}
            },
            "id": 1
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = self.session.post(url, data=json.dumps(payload), headers=headers, timeout=900)
            if response.status_code != 200:
                raise ConnectionError(f"Server Odoo ({self.url}) merespon HTTP {response.status_code}")
            res = response.json()
            if 'error' in res:
                raise Exception(res['error'].get('data', {}).get('message', res['error']))
            return res.get('result')
        except requests.exceptions.Timeout:
            raise ConnectionError(f"Koneksi ke server Odoo ({self.url}) Timeout (melewati 900 detik)")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Gagal terhubung ke server Odoo ({self.url}): {e}")

    def search_read(self, model: str, domain: List, fields: List[str] = None, limit: int = None) -> List[Dict]:
        kwargs = {}
        if fields:
            kwargs['fields'] = fields
        if limit:
            kwargs['limit'] = limit
        return self.execute_kw(model, 'search_read', [domain], kwargs)
        
    def generate_mis_report(self, instance_id: int, date_from: str, date_to: str) -> Dict[str, Any]:
        """
        Triggers MIS Builder matrix computation via JSON-RPC.
        """
        # We compute directly on the original instance_id because we no longer override the date.
        # This avoids Odoo constraint errors that occur during the 'copy' operation for hardcoded periods.
        matrix = self.execute_kw('mis.report.instance', 'compute', [[instance_id]])
        return matrix
