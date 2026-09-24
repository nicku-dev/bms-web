import re

with open('app/templates/dashboard.html', 'r') as f:
    html = f.read()

# Fix Navigation links
html = html.replace('href="#"', 'href="/"', 1)
html = html.replace('href="#"', 'href="/config"', 1)

# Swap active classes
nav_regex = re.compile(r'(<nav.*?>.*?)(</nav>)', re.DOTALL)
def nav_replacer(m):
    nav_content = m.group(1)
    
    # Dashboard Link to inactive
    nav_content = nav_content.replace(
        'border-blue-500 text-blue-600',
        'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
    )
    nav_content = nav_content.replace(
        'text-blue-500',
        'text-slate-400 group-hover:text-slate-500'
    )
    
    # Config Link to active
    nav_content = nav_content.replace(
        'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300 group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm"\n        >\n          <svg class="w-5 h-5 mr-2 text-slate-400 group-hover:text-slate-500',
        'border-blue-500 text-blue-600 group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm"\n        >\n          <svg class="w-5 h-5 mr-2 text-blue-500'
    )
    return nav_content + m.group(2)

html = nav_regex.sub(nav_replacer, html)

# Replace main content
main_regex = re.compile(r'(<main.*?>).*?(</main>)', re.DOTALL)
new_main_content = """
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold text-slate-800">Manajemen Perusahaan</h2>
      <button id="btn-add" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">+ Tambah Perusahaan</button>
    </div>
    
    <div class="bg-white shadow rounded-lg overflow-hidden">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nama Perusahaan</th>
            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Odoo Target DB</th>
            <th class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Aksi</th>
          </tr>
        </thead>
        <tbody id="company-table" class="bg-white divide-y divide-gray-200">
          <!-- Rows -->
        </tbody>
      </table>
    </div>
  </div>
  
  <script>
    async function loadCompanies() {
        const res = await fetch('/api/admin/companies');
        const data = await res.json();
        const tbody = document.getElementById('company-table');
        tbody.innerHTML = '';
        data.data.forEach(c => {
            tbody.innerHTML += `
              <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${c.id}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${c.name}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${c.target_db_name}</td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button onclick="deleteCompany(${c.id})" class="text-red-600 hover:text-red-900">Hapus</button>
                </td>
              </tr>
            `;
        });
    }
    
    async function deleteCompany(id) {
        if(confirm('Hapus perusahaan?')) {
            await fetch('/api/admin/companies/' + id, {method: 'DELETE'});
            loadCompanies();
        }
    }
    
    document.getElementById('btn-add').addEventListener('click', async () => {
        const name = prompt("Nama Perusahaan (misal FPS):");
        if(!name) return;
        const target_db_name = prompt("Nama Database Odoo Target (misal MASTER_PROD_2_1):");
        if(!target_db_name) return;
        
        await fetch('/api/admin/companies', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, target_db_name})
        });
        loadCompanies();
    });
    
    loadCompanies();
  </script>
"""
html = main_regex.sub(r'\1' + new_main_content + r'\2', html)

with open('app/templates/config.html', 'w') as f:
    f.write(html)
