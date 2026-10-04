import sys
import os
import argparse
import socket
import multiprocessing
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import uvicorn
from main import app


def is_port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def check_existing_health(host: str, port: int) -> bool:
    try:
        import urllib.request
        import json
        req = urllib.request.Request(f"http://{host}:{port}/api/health", headers={"User-Agent": "BackendProbe"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("api_running") is True or "status" in data
    except Exception:
        return False


def main():
    multiprocessing.freeze_support()

    try:
        parser = argparse.ArgumentParser(description="Local AI Document Agent Backend Server")
        parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
        parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
        parser.add_argument("--data-dir", default=None, help="Custom data directory")
        args = parser.parse_args()

        # Enforce localhost only for privacy
        if args.host not in ("127.0.0.1", "localhost"):
            print(f"[SECURITY] Enforcing binding to 127.0.0.1 for local privacy (requested: {args.host})", flush=True)
            args.host = "127.0.0.1"

        if args.data_dir:
            os.environ["DOCUMENT_AGENT_DATA_DIR"] = str(Path(args.data_dir).resolve())

        # Detect port conflicts
        if is_port_in_use(args.host, args.port):
            if check_existing_health(args.host, args.port):
                print(f"[STARTUP] Local AI Document Agent backend is already running on http://{args.host}:{args.port}", flush=True)
                sys.exit(0)
            else:
                print(f"[PORT CONFLICT] Port {args.port} is already in use by another application. Exiting gracefully.", flush=True)
                sys.exit(1)

        print(f"[STARTUP] Starting Local AI Document Agent backend on http://{args.host}:{args.port}...", flush=True)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info", access_log=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except OSError as e:
        if getattr(e, "winerror", None) == 10048 or "10048" in str(e):
            print(f"[PORT CONFLICT] Port {args.port} is already occupied: {e}")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
