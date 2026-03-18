import os


def get_evove_data_dir():
    """Return the directory for Evove data stored under ~/.local/share/evove."""
    path = os.path.join(os.path.expanduser("~"), ".local", "share", "evove")
    os.makedirs(path, exist_ok=True)
    return path
