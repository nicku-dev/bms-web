import re
with open('app/main.py', 'r') as f:
    lines = f.readlines()

in_export = False
for i, line in enumerate(lines):
    if line.startswith('    matrix = req.matrix'):
        in_export = True
    if in_export:
        if line.startswith('    except Exception as e:'):
            in_export = False
            break
        if line.startswith('    '):
            lines[i] = '    ' + line
        elif line == '\n':
            pass

with open('app/main.py', 'w') as f:
    f.writelines(lines)
