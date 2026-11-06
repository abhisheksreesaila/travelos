"""F-182 (reviewer Must 1): every environment variable the app reads is in docs/setup.md. A live site without TRAVELPAYOUTS_MARKER 404s every /go link (every Book button dead) and nothing said so.
Names built with an f-string (GITAWAY_AI_PROVIDER_<JOB>) are checked by their prefix."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "docs" / "setup.md").read_text(encoding="utf-8")
# Read by the app but not something an operator sets: the platform provides it, or fh-saas/the test seam does.
INTERNAL = {"RAILWAY_ENVIRONMENT", "RAILWAY_PUBLIC_DOMAIN"}      # Railway sets these; setup.md names them in the prose about production and the public address


def _names():
    found = {}
    for path in [ROOT / "main.py", *sorted((ROOT / "gitaway").rglob("*.py"))]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            arg = None
            if isinstance(node, ast.Call) and ast.unparse(node.func) in ("os.getenv", "os.environ.get", "os.environ.setdefault") and node.args:
                arg = node.args[0]
            elif isinstance(node, ast.Subscript) and ast.unparse(node.value) == "os.environ":
                arg = node.slice
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.setdefault(arg.value, f"{path.relative_to(ROOT)}:{node.lineno}")
            elif isinstance(arg, ast.JoinedStr) and arg.values and isinstance(arg.values[0], ast.Constant):
                found.setdefault(arg.values[0].value + "<JOB>", f"{path.relative_to(ROOT)}:{node.lineno}")      # a name built per job: its prefix is what the doc must show
    return found


def test_every_environment_variable_the_app_reads_is_in_the_setup_doc():
    names = _names()
    assert len(names) > 20, "the scan found almost nothing: it is broken"
    missing = {n: where for n, where in names.items() if n not in INTERNAL and n.replace("<JOB>", "") not in DOC}
    assert missing == {}, f"add these to the table in docs/setup.md (or to INTERNAL here, if an operator never sets them): {missing}"


def test_the_scan_sees_the_variables_that_were_missing():
    names = _names()
    for must in ("TRAVELPAYOUTS_MARKER", "TRAVELPAYOUTS_TRS", "TRAVELPAYOUTS_TOKEN", "KLOOK_FALLBACK_URL", "ANTHROPIC_API_KEY", "GITAWAY_ADMIN_EMAILS", "GITAWAY_CREATOR_IMPORT_SITE_LIMIT", "GITAWAY_AI_PROVIDER_<JOB>"):
        assert must in names, must
