from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "app"
LOCALIZED_TEXT = re.compile(r"[\u0400-\u04ff\u10a0-\u10ff]")
ALLOWED = {
    APP_ROOT / "i18n.py",
    APP_ROOT / "reference_data.py",
}
ALLOWED_DIR_PARTS = {"alembic", "tests", "__pycache__"}


def main() -> int:
    violations: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        if path in ALLOWED or any(part in ALLOWED_DIR_PARTS for part in path.parts):
            continue
        if LOCALIZED_TEXT.search(path.read_text(encoding="utf-8")):
            violations.append(str(path.relative_to(ROOT)))
    if violations:
        print("Hardcoded localized backend text found outside i18n/reference dictionaries:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
