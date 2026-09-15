from __future__ import annotations

import re
from pathlib import Path

TESTCOMPLETE_EXTENSIONS = {
    ".pjs", ".mds", ".tcNM", ".tcKDTest", ".tcScript", ".tcLS",
    ".js", ".jsx", ".vbs", ".py"
}

_ALIAS_RX = re.compile(r"\bAliases(?:\.[A-Za-z_]\w*)+")
_SYS_RX = re.compile(r"\bSys(?:\.[A-Za-z_]\w*)+")
_ACTIONS = {"Click", "DblClick", "ClickButton", "SetText", "Keys", "Check", "Uncheck", "Select", "Activate", "Close", "Exists"}


def looks_like_testcomplete(path: Path, text: str) -> bool:
    if path.suffix in {".pjs", ".mds", ".tcNM", ".tcKDTest", ".tcScript", ".tcLS"}:
        return True
    return "TestComplete" in text or "Aliases." in text or "Sys.Process(" in text


def parse_testcomplete_file(path: str, text: str) -> list[dict]:
    aliases_raw = set(_ALIAS_RX.findall(text))
    aliases = set()
    for alias in aliases_raw:
        parts = alias.split(".")
        if parts and parts[-1] in _ACTIONS:
            parts = parts[:-1]
        aliases.add(".".join(parts))
    aliases = sorted(aliases)
    sys_refs = sorted(set(_SYS_RX.findall(text)))
    refs = aliases + sys_refs
    name = Path(path).stem
    test_type = "keyword" if Path(path).suffix == ".tcKDTest" else "script"

    # Keyword tests can contain many named routines; capture likely test names without
    # binding this parser to one TestComplete file-format version.
    candidates = set(re.findall(r'(?:Name|name)="([^"]{2,120})"', text))
    test_names = sorted(n for n in candidates if not n.startswith("|"))[:200]
    if not test_names:
        test_names = [name]
    return [
        {"path": path, "name": n, "test_type": test_type, "raw_refs": refs, "aliases": aliases}
        for n in test_names
    ]
