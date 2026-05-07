import os
import shutil
from src.infrastructure.storage import get_current_username


def backup_json(src_path: str):
    """Mirror JSON saves from ~/.local/share/evove into ~/journal/evove/."""
    if not src_path:
        return
    try:
        if not os.path.exists(src_path):
            return
        backup_dir = os.path.join(os.path.expanduser("~/journal/evove"), get_current_username())
        os.makedirs(backup_dir, exist_ok=True)
        dest_path = os.path.join(backup_dir, os.path.basename(src_path))
        shutil.copy2(src_path, dest_path)
    except Exception:
        # Backup failures should not break normal saves
        return
