import json, sys
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else ".bob/tmp/pyright_bot.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)

diags = data.get("generalDiagnostics", [])
by_file = defaultdict(list)
for d in diags:
    fname = d["file"]
    if "mikrotik_bot/" in fname:
        fname = fname.split("mikrotik_bot/")[-1]
    elif "mikrotik_bot\\" in fname:
        fname = fname.split("mikrotik_bot\\")[-1]
    by_file[fname].append(d)

total_errors = 0
for fname, items in sorted(by_file.items()):
    errors = [x for x in items if x["severity"] == "error"]
    if not errors:
        continue
    total_errors += len(errors)
    print(f"=== {fname} ({len(errors)} errors) ===")
    for d in errors:
        r = d["range"]["start"]
        msg = d["message"].replace("\n", " | ")[:130]
        rule = d.get("rule", "")
        print(f"  L{r['line']+1}:{r['character']+1} [{rule}] {msg}")
    print()

print(f"TOTAL: {total_errors} errors in {len([f for f,v in by_file.items() if any(x['severity']=='error' for x in v)])} files")
