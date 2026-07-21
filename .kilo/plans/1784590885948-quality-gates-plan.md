# Quality Gates Plan

## Goal
منع دمج أي تعديل جديد إلا إذا اجتاز جميع فحوصات الجودة المعرّفة في `AGENTS.md`.

## Current State
- Repo: GitHub (`origin` exists)
- CI/CD: none
- Tools: `ruff`, `pyright`, `pytest`, `scripts/validate_handlers.py`, `py_compile`
- Python target: 3.12

## Decision
استخدم **GitHub Actions** workflow واحد على كل `push` و `pull_request` إلى `main`.

## Steps
1. أضف `pyright>=1.1.0` إلى `requirements-dev.txt`
2. أنشئ `.github/workflows/quality-gates.yml` بالخطوات التالية:
   - checkout
   - setup-python@v5 مع python-version: "3.12"
   - pip install -r requirements-dev.txt
   - `ruff check . --select F821 --exclude venv --exclude __pycache__ --exclude backups --exclude logs --exclude _releases --exclude "scripts/Activate.ps1"`
   - `py -3.12 scripts/validate_handlers.py`
   - `py -3.12 -c "import py_compile; py_compile.compile('main.py', doraise=True)"`
   - `py -3.12 -m pytest -q`
   - `py -3.12 -m pyright`
3. تأكد من أن `pyrightconfig.json` مستبعد من `alembic` و `tests`
4. شغّل الفحوصات محلياً للتأكيد قبل الرفع

## Validation
- الـ workflow يظهر في GitHub Actions
- أي فشل يمنع Merge button
- جميع الفحوصات تمر محلياً
