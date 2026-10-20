"""Static checks on the webview frontend assets.

The GUI cannot be launched in CI, so these assert the contract between
``index.html`` and ``script.js``: every element id the script touches exists,
and every inline handler in the markup is defined.
"""

import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "gui" / "assets"
HTML = (ASSETS / "index.html").read_text(encoding="utf-8")
JS = (ASSETS / "script.js").read_text(encoding="utf-8")

HTML_IDS = set(re.findall(r'id="([^"]+)"', HTML))

JS_IDS = set(re.findall(r"getElementById\('([^']+)'\)", JS))

JS_FUNCTIONS = set(re.findall(r"function ([A-Za-z_][A-Za-z0-9_]*)\s*\(", JS))

HTML_HANDLERS = set(re.findall(r'on(?:click|change)="([A-Za-z_][A-Za-z0-9_]*)\s*\(', HTML))
JS_HANDLERS = set(re.findall(r'onclick="([A-Za-z_][A-Za-z0-9_]*)\s*\(', JS))


def test_script_ids_exist_in_html():
    missing = sorted(JS_IDS - HTML_IDS)
    assert not missing, f"script.js references ids missing from index.html: {missing}"


def test_inline_handlers_are_defined():
    missing = sorted((HTML_HANDLERS | JS_HANDLERS) - JS_FUNCTIONS)
    assert not missing, f"handlers referenced but not defined in script.js: {missing}"


def test_no_cdn_dependency():
    assert "cdn.jsdelivr.net" not in HTML, "index.html must not depend on a CDN (offline requirement)"
    assert 'href="tailwind.css"' in HTML
