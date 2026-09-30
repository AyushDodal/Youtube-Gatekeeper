"""Explicit local launcher: no elevation, scheduled tasks, or hidden persistence."""
import ctypes
import os
import sys

import uvicorn

from backend.config import ROOT, load_settings


def main():
    settings = load_settings()
    if not settings.dry_run and (os.name != "nt" or not ctypes.windll.shell32.IsUserAnAdmin()):
        print("YouTube Gatekeeper needs an Administrator terminal to modify Windows hosts.")
        print("Right-click Start.cmd and choose Run as administrator, or use Start-preview.cmd for simulation.")
        return 1
    if not (ROOT / "frontend/dist/index.html").exists():
        print("Build the frontend first: run Setup.cmd or run npm.cmd run build in frontend.")
        return 1
    print("YouTube Gatekeeper: http://127.0.0.1:8000")
    print("SIMULATION: Windows hosts will not change." if settings.dry_run else "REAL BLOCKING: keep this window running for automatic expiry.")
    print("Press Ctrl+C to stop and restore the block. No service is installed.")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, workers=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
