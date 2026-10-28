import os
import threading
import unicodedata

from PyQt5.QtCore import QFileInfo
from PyQt5.QtWidgets import QFileIconProvider

INDEX = []
_LOCK = threading.Lock()
_ICON_PROVIDER = None
_ICON_CACHE = {}

SKIP_DIRS = {
    "windows kits",
    "common files",
    "microsoft sdks",
    "reference assemblies",
    "microsoft visual studio",
    "windows defender",
    "internet explorer",
    "windowsapps",
    "windows security",
}


def _norm(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")


def _add(base, name, path):
    lower = path.lower()
    with _LOCK:
        for entry in INDEX:
            if entry["path"].lower() == lower:
                return
        INDEX.append({"name": name, "path": path})


def _index_folder(base):
    if not os.path.isdir(base):
        return
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.lower().startswith(".")]
        for fname in files:
            if fname.lower().endswith((".lnk", ".exe")):
                full = os.path.join(root, fname)
                _add(base, os.path.splitext(fname)[0], full)


def _index_program_files(base, max_depth=3):
    if not os.path.isdir(base):
        return
    for root, dirs, files in os.walk(base):
        depth = root[len(base):].count(os.sep)
        if depth > max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.lower().startswith(".")]
        for fname in files:
            if fname.lower().endswith(".exe"):
                full = os.path.join(root, fname)
                _add(base, os.path.splitext(fname)[0], full)


def build_index():
    global _ICON_PROVIDER
    _ICON_PROVIDER = QFileIconProvider()
    start1 = os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    start2 = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    for folder in (start1, start2, desktop):
        _index_folder(folder)
    for pf in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
        _index_program_files(pf)


def search(query, limit=8):
    q = _norm(query).strip().lower()
    if not q:
        return []
    matches = []
    with _LOCK:
        for entry in INDEX:
            name = _norm(entry["name"]).lower()
            if q in name:
                matches.append((name.startswith(q), name, entry))
    matches.sort(key=lambda t: (not t[0], t[1]))
    return [entry for _, _, entry in matches[:limit]]


def icon_for(path):
    global _ICON_PROVIDER
    if _ICON_PROVIDER is None:
        _ICON_PROVIDER = QFileIconProvider()
    lower = path.lower()
    if lower not in _ICON_CACHE:
        _ICON_CACHE[lower] = _ICON_PROVIDER.icon(QFileInfo(path))
    return _ICON_CACHE[lower]
