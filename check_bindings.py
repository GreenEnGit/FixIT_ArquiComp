import os
import ast
import re

print("Iniciando análisis profundo de lógica HTML vs PY...\n")

# Map of endpoints to their templates
# Hardcoded for the most critical forms in this project
checks = [
    {"py": "routers/users.py", "route": "/users/new", "html": "templates/users.html"},
    {"py": "routers/inventory.py", "route": "/new", "html": "templates/inventory_sales.html"},
    {"py": "routers/customers.py", "route": "/customers/new", "html": "templates/customers.html"},
    {"py": "routers/tickets.py", "route": "/{ticket_id}/parts", "html": "templates/ticket_detail.html"},
    {"py": "main.py", "route": "/intake", "html": "templates/intake.html"},
    {"py": "main.py", "route": "/knowledge/new", "html": "templates/knowledge.html"}
]

errors_found = 0

for check in checks:
    py_file = check["py"]
    html_file = check["html"]
    
    if not os.path.exists(py_file) or not os.path.exists(html_file):
        continue
        
    # 1. Parse Python to find Form parameters
    with open(py_file, "r", encoding="utf-8") as f:
        py_content = f.read()
    
    tree = ast.parse(py_content)
    form_params = []
    
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.FunctionDef):
            # Check decorators for the route
            is_target_route = False
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and hasattr(dec.func, 'attr'):
                    # e.g. @router.post("/users/new")
                    if len(dec.args) > 0 and isinstance(dec.args[0], ast.Constant):
                        if dec.args[0].value == check["route"]:
                            is_target_route = True
                            break
            
            if is_target_route:
                # Extract parameters with Form(...) or File(...)
                for arg in node.args.args:
                    arg_name = arg.arg
                    if arg_name in ["request", "user", "db"]: continue
                    
                    form_params.append(arg_name)

    # 2. Parse HTML to find name="..."
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
        
    # Find all name="something" or name='something'
    html_names = re.findall(r'name=["\']([^"\']+)["\']', html_content)
    
    print(f"Analizando ruta {check['route']} ({py_file} -> {html_file})")
    
    for param in form_params:
        if param not in html_names:
            print(f"  [ERROR] Parámetro '{param}' requerido en PY pero no encontrado en HTML.")
            errors_found += 1
        else:
            print(f"  [OK] Parámetro '{param}' coincide.")
            
    print("-" * 40)

if errors_found == 0:
    print("\nRESULTADO: No se encontraron discrepancias. La lógica Formulario -> Servidor es correcta.")
else:
    print(f"\nRESULTADO: Se encontraron {errors_found} errores de lógica.")
