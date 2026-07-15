"""Tests for scripts/validate_routeros_paths.py (v6/v7 integration guard)."""

import ast
import importlib.util
from pathlib import Path


_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_routeros_paths.py"
_spec = importlib.util.spec_from_file_location("validate_routeros_paths", _SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def _first_call(src: str) -> ast.Call:
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            return node
    raise AssertionError("no call found")


def test_command_literal_plain_string():
    call = _first_call('mikrotik_api.execute(rk, "ip/hotspot/user/print")')
    assert guard._command_literal(call) == "ip/hotspot/user/print"


def test_command_literal_fstring_keeps_constant_parts():
    call = _first_call('mikrotik_api.execute(rk, f"{base}/user/print")')
    assert guard._command_literal(call) == "/user/print"


def test_command_literal_none_for_no_command_arg():
    call = _first_call("mikrotik_api.execute(rk)")
    assert guard._command_literal(call) is None


def test_scan_file_flags_hardcoded_userman(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text('mikrotik_api.execute(rk, "user-manager/user/print")', encoding="utf-8")
    violations = guard._scan_file(bad)
    assert violations == [(1, "user-manager/user/print")]


def test_scan_file_flags_hardcoded_v6_userman(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text('mikrotik_api.execute_long(rk, "tool/user-manager/profile/print")', encoding="utf-8")
    assert guard._scan_file(bad) == [(1, "tool/user-manager/profile/print")]


def test_scan_file_allows_central_helper_pattern(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text(
        'base = mikrotik_api.get_userman_base_path(rk)\n'
        'mikrotik_api.execute(rk, f"{base}/user/print")\n',
        encoding="utf-8",
    )
    assert guard._scan_file(ok) == []


def test_main_passes_on_real_core():
    """The current core/ must be clean (no hardcoded User Manager paths)."""
    guard.main()  # exits(1) on violation; returning means the codebase is clean
