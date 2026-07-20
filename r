# Ruff configuration for MikroTik Telegram Bot
# AGENTS.md requires: zero style/bugs errors, py312 target.
# Rules selected: E (pycodestyle errors), F (pyflakes), W (warnings),
# I (isort), UP (pyupgrade), B (flake8-bugbear).

target-version = "py312"
line-length = 100

[lint]
extend-select = ["E", "F", "W", "I", "UP", "B"]

[lint.isort]
known-first-party = ["bot", "core", "database", "utils", "pdf"]

[lint.per-file-ignores]
# scripts/* uses sys.path.insert before local imports (E402 expected)
"scripts/*" = ["E402"]
# tests/* fixtures may inject sys.path and use module-level imports after
"tests/*" = ["E402", "S101"]
# alembic migrations are auto-generated
"alembic/versions/*" = ["E", "F", "W", "I", "UP", "B"]
# bot/__init__.py re-exports symbols for backward compatibility
"bot/__init__.py" = ["F401"]
# main.py entry point may have side-effect imports
"main.py" = ["F401"]