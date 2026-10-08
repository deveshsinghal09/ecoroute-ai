"""Check tracked files for obvious credential accidents without printing matched content."""
import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
]


def main() -> int:
    result = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True)
    failures = []
    for name in result.stdout.decode().split("\0"):
        if not name:
            continue
        path = Path(name)
        forbidden = (path.name.startswith(".env") and path.name != ".env.example") or (
            path.suffix in {".pem", ".key", ".p12", ".pfx"}
        )
        if forbidden or any(pattern.search(path.read_bytes()) for pattern in PATTERNS):
            failures.append(name)
    print("FAIL: review tracked files: " + ", ".join(failures) if failures
          else "PASS: no obvious credentials in tracked files (not a complete secret audit)")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
