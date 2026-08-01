import ast
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

skip_dirs = {'.venv', 'venv', '__pycache__', 'scripts', 'node_modules', 'alembic'}

issues = []

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.normpath(os.path.join(root, fname))
        if fpath.startswith('tests/') or fpath.startswith('scripts/'):
            continue
        try:
            with open(fpath, encoding='utf-8') as f:
                source = f.read()
            tree = ast.parse(source, filename=fpath)
            lines = source.splitlines()
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type and isinstance(node.type, ast.Name) and node.type.id == 'Exception':
                    # Found an except Exception block
                    body_start = node.body[0].lineno - 1
                    body_end = node.body[-1].end_lineno if hasattr(node.body[-1], 'end_lineno') else body_start + 10
                    body_end = min(body_end, len(lines))
                    body_lines = lines[body_start:body_end]
                    body_text = '\n'.join(body_lines)
                    
                    has_exception_log = 'logger.exception' in body_text
                    has_exc_info = 'exc_info=True' in body_text or 'exc_info=1' in body_text
                    
                    exc_name = None
                    if hasattr(node, 'name') and node.name:
                        exc_name = node.name
                    
                    if exc_name:
                        logger_calls_pattern = re.compile(
                            rf'logger\.(warning|error|info|debug)\([^)]*{exc_name}[^)]*\)'
                        )
                        if logger_calls_pattern.search(body_text) and not has_exception_log and not has_exc_info:
                            issues.append(f"LOG_LOSS: {fpath}:{node.lineno}: {lines[node.lineno-1].strip()[:100]}")
                            issues.append(f"  Body: {' | '.join(body_lines[:3])}")
                    
                    if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                        issues.append(f"SILENT_PASS: {fpath}:{node.lineno}: except Exception: pass")
                    
                    line_text = lines[node.lineno-1] if node.lineno-1 < len(lines) else ''
                    if 'BLE001' in line_text:
                        after_ble001 = line_text.split('BLE001')[-1].strip()
                        if not after_ble001 or not after_ble001.startswith('-'):
                            if not after_ble001:
                                issues.append(f"BLE001_NO_EXPLANATION: {fpath}:{node.lineno} (empty after BLE001)")

# Print issues
print(f"\n=== Issues Found ({len(issues)}) ===")
for issue in issues:
    print(f"  {issue}")
