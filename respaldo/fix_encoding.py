# -*- coding: utf-8 -*-
"""
SCRIPT DE ARREGLO - Agrega encoding UTF-8 a todos los archivos Python
Ejecutar desde la carpeta de proyectos: python fix_encoding.py
"""
import os
import sys

files_to_fix = [
    'daily_market_snapshot.py',
    'generate_daily_report.py', 
    'html_formatter.py',
    'send_email_v2.py',
    'curator.py',
    'client_manager.py',
    'dashboard_server.py'
]

encoding_header = '''# -*- coding: utf-8 -*-
import sys
import io
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

'''

print("="*80)
print("ARREGLANDO ENCODING UTF-8 EN ARCHIVOS PYTHON")
print("="*80)
print()

for filename in files_to_fix:
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Si ya tiene el header, skip
        if 'sys.stdout = io.TextIOWrapper' in content:
            print(f'[SKIP] {filename} - ya tiene encoding fix')
            continue
            
        # Agregar header
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(encoding_header + content)
        
        print(f'[OK] {filename} - encoding UTF-8 agregado')
    else:
        print(f'[WARN] {filename} - archivo no encontrado')

print()
print("="*80)
print("PROCESO COMPLETADO")
print("="*80)
print()
print("Ahora puedes correr:")
print("  python daily_market_snapshot.py AM")
print("  python generate_daily_report.py AM")
print("  python html_formatter.py")
print("  python send_email_v2.py auto")
