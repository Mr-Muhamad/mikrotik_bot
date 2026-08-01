import ast
import os

results = []
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'venv', '.venv', 'node_modules', 'alembic')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=fpath)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                exc_type = 'bare'
                if node.type:
                    if isinstance(node.type, ast.Name):
                        exc_type = node.type.id
                    elif isinstance(node.type, ast.Tuple):
                        names = [e.id for e in node.type.elts if isinstance(e, ast.Name)]
                        exc_type = ', '.join(names)
                    else:
                        exc_type = ast.unparse(node.type)
                
                result = {
                    'file': fpath,
                    'line': node.lineno,
                    'type': exc_type,
                }
                results.append(result)

# Only show project files (exclude site-packages)
for r in results:
    if 'site-packages' not in r['file']:
        print(f"{r['file']}:{r['line']} -> except {r['type']}")
