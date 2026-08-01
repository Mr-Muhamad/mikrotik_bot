import os
import re
import sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Search for patterns in project source files only
skip_dirs = {'.venv', 'venv', '__pycache__', 'scripts', 'node_modules', 'alembic'}
skip_files = {os.path.normpath('find_exceptions.py'), os.path.normpath('audit_search.py')}

results = {
    'except Exception': [],
    'bare except': [],
    'except Exception: pass': [],
    'noqa': [],
    'type_ignore': [],
    'type(error_message)': [],
    'logger.error(str(': [],
    'logger.warning(str(': [],
    'logger.info(str(': [],
    'logger.debug(str(': [],
}

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.normpath(os.path.join(root, fname))
        if fpath in skip_files:
            continue
        try:
            with open(fpath, encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip test files for now (we'll check them separately)
            is_test = 'tests/' in fpath or 'scripts/' in fpath
            if is_test:
                continue

            if 'except Exception' in stripped:
                results['except Exception'].append(f"{fpath}:{i}: {stripped}")
            if re.match(r'except\s*:', stripped):
                results['bare except'].append(f"{fpath}:{i}: {stripped}")
            if 'except Exception' in stripped and 'pass' in stripped:
                results['except Exception: pass'].append(f"{fpath}:{i}: {stripped}")
            if '# noqa' in stripped:
                results['noqa'].append(f"{fpath}:{i}: {stripped}")
            if '# type: ignore' in stripped:
                results['type_ignore'].append(f"{fpath}:{i}: {stripped}")
            if 'type(' in stripped and 'error_message' in stripped.lower():
                results['type(error_message)'].append(f"{fpath}:{i}: {stripped}")
            for level in ['error', 'warning', 'info', 'debug']:
                if f'logger.{level}(str(' in stripped:
                    results[f'logger.{level}(str('].append(f"{fpath}:{i}: {stripped}")

# Print results
for key, items in results.items():
    if items:
        print(f"\n=== {key} ({len(items)} occurrences) ===")
        for item in items:
            print(f"  {item}")
