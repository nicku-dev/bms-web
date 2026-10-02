from collections import defaultdict
from typing import Dict, Any

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
        safe_env = defaultdict(float, env_vars)
        
        # Inject MIS queries (e.g., cap_query.debit, tbab.sumq1_25)
        safe_env.update(self.query_vars)
        
        try:
            val = eval(expr, {}, safe_env)
            val = float(val)
            
            # Auto-proportional logic for Indirect Costs
            if is_expense and 'prop_tpj' not in expr:
                # If the formula references any query variable, we multiply by prop_tpj
                if any(q in expr for q in self.query_vars.keys()):
                    val = val * safe_env.get('prop_tpj', 0.0)
                    
            return val
        except Exception as e:
            # We must raise it so the caller (compiler) can catch it and `continue`,
            # thereby NOT overwriting the existing cell value with 0.0 or None.
            raise ValueError(f"Failed to evaluate '{expr}': {str(e)}")
