import sys
import os
import subprocess

try:
    from waitress import serve
except Exception:
    serve = None

# Add current directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def run():
    app_path = os.path.join("roko_evoveby", "src", "components", "services", "web_service", "app.py")
    print(f"Starting Evove Web Service from {app_path}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.dirname(__file__))
    try:
        if serve is not None:
            # Run with waitress to allow configurable timeouts
            from src.components.services.web_service.app import app
            serve(app, host="0.0.0.0", port=5000, channel_timeout=120)
        else:
            print("Waitress not installed; falling back to Flask dev server.")
            subprocess.run([sys.executable, app_path], check=True, env=env)
    except KeyboardInterrupt:
        print("\nWeb service stopped.")

if __name__ == "__main__":
    run()
