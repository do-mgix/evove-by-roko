from pathlib import Path
import os
import sys
import subprocess

try:
    from waitress import serve
except Exception:
    serve = None

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_MODULE_PATH = REPO_ROOT / "src" / "interfaces" / "web" / "app.py"
sys.path.append(str(REPO_ROOT))


def run():
    print(f"Starting Evove Web Service from {APP_MODULE_PATH}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    try:
        if serve is not None:
            from src.interfaces.web.app import app
            serve(app, host="0.0.0.0", port=5000, channel_timeout=120)
        else:
            print("Waitress not installed; falling back to Flask dev server.")
            subprocess.run([sys.executable, str(APP_MODULE_PATH)], check=True, env=env)
    except KeyboardInterrupt:
        print("\nWeb service stopped.")


if __name__ == "__main__":
    run()
