"""Build Linux x86_64 wheels without Docker or AWS; never copies local credentials."""
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "build" / "lambda"
if target.exists():
    # Fixed repository-contained build output only, never a user-configurable deletion path.
    if target.is_symlink() or target.resolve() != root / "build" / "lambda":
        raise RuntimeError("Refusing unexpected build path")
    shutil.rmtree(target)
target.mkdir(parents=True)
subprocess.run([
    sys.executable, "-m", "pip", "install", "--target", str(target),
    "--platform", "manylinux2014_x86_64", "--implementation", "cp", "--python-version", "3.11",
    "--abi", "cp311", "--only-binary=:all:", "--no-compile",
    "-r", str(root / "requirements-runtime.txt"), "-c", str(root / "requirements.lock"),
], check=True)
shutil.copytree(root / "src" / "ecoroute", target / "ecoroute",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
size = sum(p.stat().st_size for p in target.rglob("*") if p.is_file())
if size >= 250 * 1024 * 1024:
    raise RuntimeError("Lambda package exceeds uncompressed limit")
print(f"Lambda Linux asset built: {size / 1024 / 1024:.1f} MiB")
