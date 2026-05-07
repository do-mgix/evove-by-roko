import os

_DEFAULT_USERNAME = "default"
_current_username = os.environ.get("EVOVE_USERNAME", _DEFAULT_USERNAME)
_LEGACY_FILES = (
    "user.json",
    "logs.json",
    "sequences.json",
    "sleep_data.json",
    "fountain.json",
)


def get_evove_root_dir():
    path = os.path.join(os.path.expanduser("~"), ".local", "share", "evove")
    os.makedirs(path, exist_ok=True)
    return path


def normalize_username(username: str) -> str:
    cleaned = "".join(
        ch for ch in str(username or "").strip()
        if ch.isalnum() or ch in ("_", "-")
    )
    return cleaned[:24]


def set_current_username(username: str) -> str:
    global _current_username
    normalized = normalize_username(username) or _DEFAULT_USERNAME
    _current_username = normalized
    os.environ["EVOVE_USERNAME"] = normalized
    return normalized


def get_current_username() -> str:
    return _current_username


def migrate_legacy_root_data():
    root = get_evove_root_dir()
    legacy_paths = [os.path.join(root, name) for name in _LEGACY_FILES if os.path.exists(os.path.join(root, name))]
    if not legacy_paths:
        return

    default_dir = os.path.join(root, _DEFAULT_USERNAME)
    os.makedirs(default_dir, exist_ok=True)
    for src_path in legacy_paths:
        dest_path = os.path.join(default_dir, os.path.basename(src_path))
        if os.path.exists(dest_path):
            continue
        os.replace(src_path, dest_path)


def get_evove_data_dir():
    """Return the active user directory under ~/.local/share/evove/<username>.

    Uses the process-wide current username (CLI-style). For multi-user web
    contexts, prefer get_user_data_dir(username).
    """
    migrate_legacy_root_data()
    path = os.path.join(get_evove_root_dir(), get_current_username())
    os.makedirs(path, exist_ok=True)
    return path


def get_user_data_dir(username: str):
    """Return the per-user data directory without touching process globals.

    Safe for concurrent multi-user requests (e.g., FastAPI handlers).
    """
    name = normalize_username(username) or _DEFAULT_USERNAME
    path = os.path.join(get_evove_root_dir(), name)
    os.makedirs(path, exist_ok=True)
    return path
