from pathlib import Path


def get_user_home_dir() -> str:
    """
    Returns the absolute path of the current user's HOME directory.
    """
    return str(Path.home().resolve())