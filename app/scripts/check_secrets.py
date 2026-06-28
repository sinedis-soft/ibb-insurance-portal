from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".json", ".yml", ".yaml", ".md", ".txt", ".example"}
SKIP_PARTS = {".codex", ".git", ".pytest_cache", ".ruff_cache", ".next", "node_modules", "__pycache__", "storage"}
BITRIX_WEBHOOK_URL = re.compile(r"https?://[^\s\"']+bitrix24\.[^\s\"']+/rest/\d+/[A-Za-z0-9_-]{12,}")
LEGACY_WEBHOOK_ENV = re.compile(r"BITRIX_WEBHOOK_URL\s*=")
TOKEN_ASSIGNMENT = re.compile(r"BITRIX24_WEBHOOK_TOKEN\s*=\s*(?!replace_me|test-token|\"|\{)[A-Za-z0-9_-]{12,}")

ALLOWLIST = {
    Path("tests/conftest.py"),
    Path("tests/test_external_service_config.py"),
    Path("app/scripts/check_secrets.py"),
}


def should_scan(path: Path) -> bool:
    relative_parts = set(path.relative_to(ROOT).parts)
    if relative_parts & SKIP_PARTS:
        return False
    if path.name == ".env.example":
        return True
    return path.suffix in SCANNED_SUFFIXES


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_scan(path):
            continue
        relative = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="ignore")
        if BITRIX_WEBHOOK_URL.search(text):
            findings.append(f"{relative}: likely Bitrix24 webhook URL")
        if relative not in ALLOWLIST and LEGACY_WEBHOOK_ENV.search(text):
            findings.append(f"{relative}: legacy BITRIX_WEBHOOK_URL env is not allowed")
        if TOKEN_ASSIGNMENT.search(text):
            findings.append(f"{relative}: likely hardcoded Bitrix24 token")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8", errors="ignore")
    if ".env" not in gitignore or ".env*.local" not in gitignore:
        findings.append(".gitignore: local env files must be ignored")
    if findings:
        print("Potential secret issues found:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Secret check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
