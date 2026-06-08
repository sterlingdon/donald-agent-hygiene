import os


def default_home() -> str:
    return os.path.expanduser("~")


def cc_projects(home: str) -> str:
    return os.path.join(home, ".claude", "projects")


def codex_home(home: str) -> str:
    return os.path.join(home, ".codex")


def codex_sessions(home: str) -> str:
    return os.path.join(home, ".codex", "sessions")
