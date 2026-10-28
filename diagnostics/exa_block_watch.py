"""Watch whether the Exa API stops blocking this network.

The Exa API answers HTTP 403 for this IP range (Cloudflare blocks whole
networks, not single keys). While that lasts the backend falls back to the
local SearXNG instance, so the only thing worth watching is the moment the
block is lifted — after that the primary provider takes over on its own.

The script prints one verdict line:

    STATUS=BLOCKED  (HTTP 403)
    STATUS=RECOVERED (HTTP 200)

and keeps the previous verdict in diagnostics/exa_block_state.json, so the
caller can tell a change from a repetition. The probe is a single request
with numResults=1 — it is deliberately rare, because the blocked address is
the very one that is being throttled.

Run: python diagnostics/exa_block_watch.py
"""

import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(ROOT, "diagnostics", "exa_block_state.json")
PROBE_URL = "https://api.exa.ai/search"
TIMEOUT = 20


def read_api_key() -> str:
    """Read EXA_API_KEY from .env without printing it."""
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        return ""
    with open(env_path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("EXA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def probe() -> tuple[int, str]:
    """Return (status code, note). A network failure is not a recovery."""
    headers = {"Content-Type": "application/json"}
    key = read_api_key()
    if key:
        headers["x-api-key"] = key
    try:
        response = requests.post(
            PROBE_URL,
            headers=headers,
            json={"query": "health probe", "numResults": 1},
            timeout=TIMEOUT,
        )
    except Exception as e:
        return 0, f"request failed: {e}"
    return response.status_code, ""


def main() -> int:
    status_code, note = probe()
    blocked = status_code != 200
    verdict = "BLOCKED" if blocked else "RECOVERED"

    previous = load_state()
    changed = previous.get("status") != verdict

    state = {
        "status": verdict,
        "http_status": status_code,
        "note": note,
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "changed": changed,
    }
    save_state(state)

    print(f"STATUS={verdict} (HTTP {status_code}) changed={str(changed).lower()}")
    if note:
        print(f"NOTE={note}")
    if changed:
        print(f"PREVIOUS={previous.get('status', 'unknown')} at {previous.get('checked_at', 'never')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
