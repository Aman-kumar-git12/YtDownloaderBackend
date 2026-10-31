"""Free Cloudflare WARP proxy for YouTube requests.

YouTube blocks most datacenter IPs (Render, AWS...) with "Sign in to confirm you're
not a bot". On startup this downloads two small open-source tools (checksum-verified),
creates a free WARP account and runs a local SOCKS5 proxy through it, so YouTube sees
a Cloudflare IP instead. If anything fails the server simply keeps connecting directly.

Disable with USE_WARP=0. Ignored when YOUTUBE_PROXY is set.
"""
import hashlib
import io
import os
import platform
import subprocess
import tarfile
import tempfile
import threading
import time

import requests
import yt_dlp

WGCF_VERSION = "2.3.1"
WIREPROXY_VERSION = "1.1.3"
CHECKSUMS = {
    "amd64": {
        "wgcf": "4fb7a136aa470ece11d17949c7db07b040ec9c604742dc8680bcf1889f85d0c8",
        "wireproxy": "e88c1d090740373fc606c1bafd81d9a5eadc642cce5667616e20e9d7a444f51c",
    },
    "arm64": {
        "wgcf": "710ab2d8ac145d81a4cf0c11bdb0e05914f77ae2a45f67b87e718d84b4cb7301",
        "wireproxy": "370e00bd2167960d1ecd1c3c1439715bbaa94a0a110a2040468670c9af6021b6",
    },
}
PROXY_URL = "socks5://127.0.0.1:40000"
WORK_DIR = os.path.join(tempfile.gettempdir(), "warp")

status = {"enabled": False, "state": "not started", "error": None}
_process = None


def proxy_url():
    """The WARP proxy URL while it's running, else None."""
    if status["state"] == "running" and _process and _process.poll() is None:
        return PROXY_URL
    return None


def start_in_background():
    if os.getenv("USE_WARP", "1") == "0" or os.getenv("YOUTUBE_PROXY"):
        status["state"] = "disabled"
        return
    if platform.system() != "Linux":
        status["state"] = "skipped (only runs on Linux servers)"
        return
    status["enabled"] = True
    threading.Thread(target=_start, name="warp-setup", daemon=True).start()


def _start():
    global _process
    try:
        status["state"] = "downloading"
        arch = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}[platform.machine().lower()]
        os.makedirs(WORK_DIR, exist_ok=True)

        wgcf = _download(
            f"https://github.com/ViRb3/wgcf/releases/download/v{WGCF_VERSION}/wgcf_{WGCF_VERSION}_linux_{arch}",
            CHECKSUMS[arch]["wgcf"],
        )
        _write_executable("wgcf", wgcf)
        archive = _download(
            f"https://github.com/windtf/wireproxy/releases/download/v{WIREPROXY_VERSION}/wireproxy_linux_{arch}.tar.gz",
            CHECKSUMS[arch]["wireproxy"],
        )
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            _write_executable("wireproxy", tar.extractfile("wireproxy").read())

        status["state"] = "registering"
        wgcf_path = os.path.join(WORK_DIR, "wgcf")
        if not os.path.exists(os.path.join(WORK_DIR, "wgcf-account.toml")):
            subprocess.run([wgcf_path, "register", "--accept-tos"], cwd=WORK_DIR, check=True,
                           capture_output=True, timeout=60)
        subprocess.run([wgcf_path, "generate"], cwd=WORK_DIR, check=True, capture_output=True, timeout=60)

        config = os.path.join(WORK_DIR, "wireproxy.conf")
        with open(config, "w") as f:
            f.write(f"WGConfig = {os.path.join(WORK_DIR, 'wgcf-profile.conf')}\n\n"
                    "[Socks5]\nBindAddress = 127.0.0.1:40000\n")

        status["state"] = "connecting"
        _process = subprocess.Popen([os.path.join(WORK_DIR, "wireproxy"), "-c", config],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        last_err = None
        for _ in range(15):
            time.sleep(2)
            try:
                with yt_dlp.YoutubeDL({"proxy": PROXY_URL, "quiet": True, "socket_timeout": 10}) as ydl:
                    trace = ydl.urlopen("https://www.cloudflare.com/cdn-cgi/trace").read().decode()
                if "warp=on" in trace or "warp=plus" in trace:
                    status["state"] = "running"
                    print("🌐 [WARP] Proxy running — YouTube requests now go through Cloudflare WARP")
                    return
                last_err = "connected but WARP is not active"
            except Exception as e:
                last_err = str(e)
        raise RuntimeError(f"proxy never came up: {last_err}")
    except Exception as e:
        status.update(state="failed", error=str(e)[:300])
        if _process:
            _process.kill()
        print(f"⚠️ [WARP] Not available, connecting directly instead: {e}")


def _download(url, sha256):
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.content
    if hashlib.sha256(data).hexdigest() != sha256:
        raise RuntimeError(f"checksum mismatch for {url}")
    return data


def _write_executable(name, data):
    path = os.path.join(WORK_DIR, name)
    with open(path, "wb") as f:
        f.write(data)
    os.chmod(path, 0o755)
