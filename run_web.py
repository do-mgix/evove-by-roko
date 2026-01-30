import sys
import os
import subprocess

# Add current directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

def run():
    app_path = os.path.join("roko_evoveby", "src", "components", "services", "web_service", "app.py")
    print(f"Starting Evove Web Service from {app_path}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.abspath(os.path.dirname(__file__))
    try:
        subprocess.run([sys.executable, app_path], check=True, env=env)
    except KeyboardInterrupt:
        print("\nWeb service stopped.")

if __name__ == "__main__":
    run()
