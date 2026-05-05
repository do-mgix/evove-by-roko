from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO_ROOT))

from src.interfaces.cli.user_selector import select_user_profile


def main():
    while True:
        select_user_profile()
        from src.interfaces.cli.system import dial_start
        result = dial_start()
        if result != "user_selection":
            break


if __name__ == "__main__":
    main()
