"""Read-only Android USB/nRF metadata check; never reads health data or device identifiers."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", help="Optional local path to Android platform-tools adb")
    args = parser.parse_args()
    default = Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"
    adb = args.adb or shutil.which("adb") or (str(default) if default.is_file() else None)
    if not adb:
        print(json.dumps({"status": "adb_missing", "action": "Install Android SDK Platform-Tools from developer.android.com"}))
        return 1

    def run(*command):
        return subprocess.run([adb, *command], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)

    result = run("devices")
    if result.returncode:
        print(json.dumps({"status": "adb_unavailable", "action": "Check the platform-tools installation"}))
        return 1
    states = [row.split()[1] for row in result.stdout.splitlines() if "\t" in row]
    if states != ["device"]:
        print(json.dumps({"status": "phone_not_ready", "connected_count": len(states), "states": states,
                          "action": "Connect one phone, enable USB debugging, unlock and accept this laptop's RSA prompt"}))
        return 1
    installed = run("shell", "pm", "list", "packages", "no.nordicsemi.android.mcp")
    print(json.dumps({"status": "authorized", "nrf_connect_installed": "package:no.nordicsemi.android.mcp" in installed.stdout,
                      "health_data_verified": False, "note": "USB debugging is not a health-data bridge; verify watch services and a documented adapter"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
