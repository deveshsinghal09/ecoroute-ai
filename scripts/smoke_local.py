"""Start a temporary loopback server, verify health and stop it."""
import json
import subprocess
import sys
import time
import urllib.request
from urllib.error import HTTPError


def main():
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "ecoroute.main:app", "--host", "127.0.0.1",
         "--port", "8765", "--no-access-log"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if process.poll() is not None:
                raise RuntimeError("Server exited before health check; check port 8765")
            try:
                with urllib.request.urlopen("http://127.0.0.1:8765/healthz", timeout=1) as response:
                    payload = json.load(response)
                    assert response.status == 200
                    assert payload["phase"] == "1-foundation"
                    assert payload["live_domain_providers"] is False
                    with urllib.request.urlopen("http://127.0.0.1:8765/api/v1/health", timeout=2) as health:
                        assert health.status == 200
                    with urllib.request.urlopen("http://127.0.0.1:8765/docs", timeout=2) as docs:
                        assert docs.status == 200
                    try:
                        urllib.request.urlopen("http://127.0.0.1:8765/api/v1/alerts/preferences", timeout=2)
                        raise AssertionError("Protected endpoint accepted missing token")
                    except HTTPError as denied:
                        assert denied.code == 401
                    try:
                        with urllib.request.urlopen("http://127.0.0.1:8765/api/v1/ready", timeout=2) as ready:
                            assert ready.status == 200
                    except HTTPError as unready:
                        assert unready.code == 503
                    print("PASS: health/docs 200, protected route 401, readiness checked; server stopped")
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("Server did not become ready")
    finally:
        process.terminate()
        process.wait(timeout=5)


if __name__ == "__main__":
    main()
