from collections import defaultdict
from typing import Dict, Any

class SmartVar(float):
    """A float that safely returns itself for any sub-attribute access like ptpj.q1, total_pendapatan.q1, etc."""
    def __getattr__(self, name):
        return float(self)

class CompilerEvaluator:
    def __init__(self, query_vars: Dict[str, Any]):
        """
        query_vars contains the MIS Report Query objects injected from Odoo.
        e.g., {'trip_q1': Namespace(debit=..., credit=...)}
        """
        self.query_vars = query_vars
        
    def evaluate_algebraic(self, expr: str, env_vars: dict, is_expense: bool) -> float:
        """
        Evaluates a formula safely within the provided environment variables.
        Raises ValueError if the evaluation fails (e.g., missing variables) so the caller
        can handle it cleanly without overwriting valid data.
        """
        safe_env = defaultdict(float)
        for k, v in env_vars.items():
            if isinstance(v, (int, float)):
                safe_env[k] = SmartVar(v)
            else:
                safe_env[k] = v
        
        # Inject MIS queries (e.g., cap_query.debit, tbab.sumq1_25)
        safe_env.update(self.query_vars)
        
        try:
            val = eval(expr, {}, safe_env)
            val = float(val)
            
            return val
        except Exception as e:
            # We must raise it so the caller (compiler) can catch it and `continue`,
            # thereby NOT overwriting the existing cell value with 0.0 or None.
            print(f"Failed to evaluate '{expr}': {str(e)}")
            raise ValueError(f"Failed to evaluate '{expr}': {str(e)}")
