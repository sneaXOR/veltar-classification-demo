from __future__ import annotations

import os
import sys
import time
import urllib.error
import urllib.request


def wait_for_url(url: str, timeout_seconds: int, interval_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if 200 <= response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(interval_seconds)
    raise TimeoutError(f"Dependency did not become ready in time: {url}")


def main() -> int:
    urls = [item.strip() for item in os.environ.get("WAIT_FOR_URLS", "").split(",") if item.strip()]
    timeout_seconds = int(os.environ.get("WAIT_FOR_TIMEOUT_SECONDS", "600"))
    interval_seconds = int(os.environ.get("WAIT_FOR_INTERVAL_SECONDS", "5"))

    for url in urls:
        print(f"Waiting for dependency: {url}", flush=True)
        wait_for_url(url, timeout_seconds=timeout_seconds, interval_seconds=interval_seconds)
        print(f"Dependency ready: {url}", flush=True)

    os.execvp(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1) from exc
