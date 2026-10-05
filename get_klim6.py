import re

with open("app/compiler.py", "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'TOTAL KAPAL TERPILIH' in line.upper():
            print(f"Line {i+1}: {line.strip()}")
