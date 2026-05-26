import os
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('templates'))
templates_dir = 'templates'
has_error = False

for filename in os.listdir(templates_dir):
    if filename.endswith('.html'):
        try:
            env.get_template(filename)
            print(f"[OK] {filename}")
        except Exception as e:
            print(f"[ERROR] {filename}: {e}")
            has_error = True

if has_error:
    exit(1)
else:
    print("All templates compiled successfully!")
