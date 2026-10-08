"""Start a temporary loopback server, verify health and stop it."""
import json
import subprocess
import sys
import time
import urllib.request


def main():
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ecoroute.main:app", "--host", "127.0.0.1",
         "--port", "8765"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError("Server exited before health check; check port 8765")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/healthz", timeout=1) as response:
                    payload = json.load(response)
                    assert response.status == 200
                    assert payload["phase"] == "0-scaffold"
                    assert payload["integrations_enabled"] is False
                    print("PASS: loopback HTTP health returned 200; integrations disabled")
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("Server did not become ready")
    finally:
        process.terminate()
        process.wait(timeout=5)


if __name__ == "__main__":
    main()
