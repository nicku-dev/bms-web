import json, re

with open('../bms-reporting/debug_matrix.json') as f:
    matrix = json.load(f)

for row in matrix.get('body', []):
    for cell in row.get('cells', []):
        val_c = cell.get('val_c')
        if val_c:
            print(val_c)
