"""Keep a free Render instance awake.

Render's free plan stops a service after 15 minutes without incoming requests,
and the next visitor then waits ~30-60s for it to start. Render sets
RENDER_EXTERNAL_URL automatically; pinging our own public /health every 10
minutes counts as incoming traffic and keeps the service warm.
Disable with KEEP_ALIVE=0, or point it elsewhere with KEEP_ALIVE_URL.
"""
import os
import threading
import time

import requests

INTERVAL_SECONDS = 600
status = {"enabled": False, "last_ping": None, "last_result": None}


def start():
    base_url = os.getenv("KEEP_ALIVE_URL") or os.getenv("RENDER_EXTERNAL_URL")
    if os.getenv("KEEP_ALIVE", "1") == "0" or not base_url:
        return
    status["enabled"] = True
    url = base_url.rstrip("/") + "/health"

    def loop():
        while True:
            time.sleep(INTERVAL_SECONDS)
            try:
                code = requests.get(url, timeout=30).status_code
                status["last_result"] = f"HTTP {code}"
            except requests.RequestException as e:
                status["last_result"] = f"failed: {e}"[:200]
            status["last_ping"] = time.strftime("%H:%M:%S")

    threading.Thread(target=loop, name="keep-alive", daemon=True).start()
