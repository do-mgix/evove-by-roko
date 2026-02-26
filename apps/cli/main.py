from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT))

from src.components.services.system import dial_start


def main():
    dial_start()


if __name__ == "__main__":
    main()
