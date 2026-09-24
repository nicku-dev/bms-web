import re

with open('app/templates/config.html', 'r') as f:
    content = f.read()

# Fix Navigation
content = content.replace('href="#"', 'href="/"', 1)
content = content.replace('href="#"', 'href="/config"', 1)
content = content.replace(
    'class="border-blue-500 text-blue-600 group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm"',
    'class="border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm"'
)
content = content.replace(
    'class="border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm"',
    'class="border-blue-500 text-blue-600 group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm"'
)

# Wait, the replace above would swap them back if done sequentially and matching everything. Let's do it with regex.

