import os
import shutil


def backup_json(src_path: str):
    """Mirror JSON saves from data/ into ~/journal/evove/."""
    if not src_path:
        return
    try:
        if not os.path.exists(src_path):
            return
        backup_dir = os.path.expanduser("~/journal/evove")
        os.makedirs(backup_dir, exist_ok=True)
        dest_path = os.path.join(backup_dir, os.path.basename(src_path))
        shutil.copy2(src_path, dest_path)
    except Exception:
        # Backup failures should not break normal saves
        return
