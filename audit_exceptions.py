import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

skip_dirs = {'.venv', 'venv', '__pycache__', 'scripts', 'node_modules', 'alembic'}

# Find all except Exception blocks and check if they properly log the exception
issues = []

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.normpath(os.path.join(root, fname))
        # Skip test files and scripts for now
        if fpath.startswith('tests/') or fpath.startswith('scripts/'):
            continue
        try:
            with open(fpath, encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
        except Exception:
            continue

        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Find except Exception blocks
            if 'except Exception' in stripped:
                # Check if the next few lines contain logging
                # First check if this line already has BLE001 noqa
                has_noqa = '# noqa' in stripped
                
                # Check the body for logger calls
                start = i + 1
                end = min(i + 10, len(lines))  # Check first 10 lines after except
                body_lines = lines[start:end]
                body_text = '\n'.join(body_lines)
                
                has_exception_log = 'logger.exception(' in body_text
                has_exc_info = 'exc_info=True' in body_text
                has_pass = 'pass' in body_text.strip()
                
                if 'as e' in stripped or 'as ex' in stripped or 'as kick_err' in stripped:
                    # Has exception variable captured
                    has_var = True
                else:
                    has_var = False
                
                if not has_exception_log and not has_exc_info:
                    # Check if the exception variable is used in logging
                    if has_var and ('e)' in body_text or 'ex)' in body_text or 'exc)' in body_text):
                        # Might be using logger.warning(..., e, ...) which loses traceback
                        if 'logger.warning(' in body_text or 'logger.error(' in body_text or 'logger.info(' in body_text:
                            # Check if e is passed as positional arg to logger
                            if re.search(r'logger\.(warning|error|info|debug)\([^)]*\b[e]\b[^)]*\)', body_text.replace('\n', ' ')):
                                issues.append(f"LOG_LOSS: {fpath}:{i+1}: {stripped[:80]}")
                
                if has_pass and not has_exception_log and not has_exc_info:
                    issues.append(f"SILENT_PASS: {fpath}:{i+1}: {stripped[:80]}")
                
                # Check for type(error) where error is a string (not an exception)
                if 'type(error' in body_text or 'type(err' in body_text:
                    issues.append(f"TYPE_OF_STRING: {fpath}:{i+1}: body uses type() on string variable")

# Print issues
print(f"\n=== Potential Issues Found ({len(issues)}) ===")
for issue in issues:
    print(f"  {issue}")
