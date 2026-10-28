import ctypes
import os
import subprocess
import sys
import threading
import winreg
from ctypes import wintypes

from PyQt5.QtCore import (Qt, QEvent, QObject, QAbstractNativeEventFilter,
                          QTimer, QThread, pyqtSignal)
from PyQt5.QtGui import (QIcon, QPixmap, QPainter, QColor, QRadialGradient,
                         QPen, QCursor)
from PyQt5.QtWidgets import (QApplication, QSystemTrayIcon, QMenu,
                             QMessageBox, QFileDialog, QAction)

import config as cfgmod
import search as searchmod
import system_actions as sa
from piemenu import PieMenu

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_MAP = {"alt": MOD_ALT, "control": MOD_CONTROL, "ctrl": MOD_CONTROL,
           "shift": MOD_SHIFT, "win": MOD_WIN}
KEY_CODES = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
             "backspace": 0x08, "delete": 0x2E, "left": 0x25, "right": 0x27,
             "up": 0x26, "down": 0x28}
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "MeuLauncher"
HOTKEY_ID = 1


def resolve_key_code(key):
    if len(key) == 1 and key.isalnum():
        return ord(key.upper())
    if len(key) >= 2 and key[0].lower() == "f" and key[1:].isdigit():
        num = int(key[1:])
        if 1 <= num <= 24:
            return 0x70 + num - 1
    return KEY_CODES.get(key.lower(), 0x20)


def launch_command():
    if getattr(sys, "frozen", False):
        return '"%s"' % sys.executable
    pyw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = sys.executable
    script = os.path.abspath(sys.argv[0])
    return '"%s" "%s"' % (pyw, script)


def is_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH) as key:
            winreg.QueryValueEx(key, RUN_VALUE_NAME)
        return True
    except OSError:
        return False


def set_autostart(enable):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0,
                            winreg.KEY_SET_VALUE) as key:
            if enable:
                winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ,
                                  launch_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
                except OSError:
                    pass
    except OSError:
        pass


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.callback()
                return True, 0
        return False, 0


class ClickOutsideFilter(QObject):
    def __init__(self, pie):
        super().__init__()
        self.pie = pie

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.MouseButtonPress and self.pie.isVisible()
                and not self.pie.geometry().contains(event.globalPos())):
            self.pie.close_menu()
        return False


class IndexThread(QThread):
    done = pyqtSignal()

    def run(self):
        searchmod.build_index()
        self.done.emit()


class Launcher:
    def __init__(self, app, cfg):
        self.app = app
        self.cfg = cfg
        self.pie = PieMenu(cfg)
        self.pie.itemActivated.connect(self._on_item)
        self.pie.searchChanged.connect(self._on_search)
        self.pie.addFavoriteRequested.connect(self._on_add_favorite)
        self.pie.removeFavoriteRequested.connect(self._on_remove_favorite)
        self.click_filter = ClickOutsideFilter(self.pie)
        self.app.installEventFilter(self.click_filter)
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._run_search)
        self.index_thread = IndexThread()
        self.index_thread.start()

    def toggle_menu(self):
        if self.pie.isVisible():
            self.pie.close_menu()
        else:
            self.pie.set_sectors(self._build_sectors())
            self.pie.show_at(QCursor.pos())

    def _build_sectors(self):
        favorites = []
        for fav in self.cfg.get("favorites", []):
            item = {
                "name": fav.get("name", os.path.basename(fav.get("path", ""))),
                "favorite": True,
            }
            if "cmd" in fav:
                item["cmd"] = list(fav["cmd"])
            if "path" in fav:
                item["path"] = fav["path"]
                item["icon"] = searchmod.icon_for(fav["path"])
            favorites.append(item)
        base = [
            {"name": "Busca", "search": True, "children": []},
            {"name": "Favoritos", "children": favorites},
            {"name": "Ajustes", "action": sa.open_settings},
            {"name": "Painel", "action": sa.open_control_panel},
            {"name": "Tarefas", "action": sa.open_task_manager},
            {"name": "Desligar", "children": [
                {"name": "Reiniciar", "action": sa.restart_pc, "confirm": True},
                {"name": "Desligar", "action": sa.shutdown_pc, "confirm": True},
                {"name": "Sair", "action": sa.logoff_pc, "confirm": True},
            ]},
            {"name": "opencode", "cmd": self._opencode_cmd()},
            {"name": "Bloquear", "action": sa.lock_pc},
        ]
        count = max(1, int(self.cfg.get("sectors", 8)))
        return base[:count]

    def _opencode_cmd(self):
        npm_cmd = os.path.join(
            os.environ.get("APPDATA", ""), "npm", "opencode.cmd")
        if os.path.exists(os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "wt.exe")):
            return ["wt.exe", "-d", os.path.expanduser("~"), npm_cmd]
        return ["cmd.exe", "/k", npm_cmd]

    def _on_item(self, item):
        self.pie.close_menu()
        if item.get("confirm"):
            reply = QMessageBox.question(
                self.pie, "Confirmar", "Confirmar a acao: %s?" % item["name"])
            if reply != QMessageBox.Yes:
                return
        action = item.get("action")
        path = item.get("path")
        cmd = item.get("cmd")
        if callable(action):
            try:
                action()
                return
            except Exception:
                pass
        if cmd:
            try:
                subprocess.Popen(cmd)
            except OSError:
                pass
            return
        if path:
            try:
                os.startfile(path)
            except OSError:
                try:
                    subprocess.Popen(path, shell=True)
                except OSError:
                    pass

    def _on_search(self, text):
        self._search_timer.start(200)

    def _run_search(self):
        text = self.pie.search_edit.text()
        results = []
        for entry in searchmod.search(text):
            results.append({
                "name": entry["name"],
                "path": entry["path"],
                "icon": searchmod.icon_for(entry["path"]),
            })
        self.pie.set_search_results(results)

    def _on_add_favorite(self):
        path, _ = QFileDialog.getOpenFileName(
            self.pie, "Adicionar aplicativo", "C:\\",
            "Programas (*.exe *.lnk);;Todos os arquivos (*)")
        if not path:
            return
        favorites = self.cfg.setdefault("favorites", [])
        lower = path.lower()
        if any(f.get("path", "").lower() == lower for f in favorites):
            return
        favorites.append({"name": os.path.splitext(os.path.basename(path))[0],
                          "path": path})
        cfgmod.save(self.cfg)
        self.pie.set_sectors(self._build_sectors())

    def _on_remove_favorite(self, item):
        favorites = self.cfg.get("favorites", [])
        lower = item.get("path", "").lower()
        favorites[:] = [f for f in favorites
                        if f.get("path", "").lower() != lower]
        cfgmod.save(self.cfg)
        self.pie.set_sectors(self._build_sectors())

    def refresh_favorites(self):
        self.pie.set_sectors(self._build_sectors())


def make_tray_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    grad = QRadialGradient(32, 32, 30)
    grad.setColorAt(0, QColor("#2563eb"))
    grad.setColorAt(1, QColor("#7c3aed"))
    painter.setPen(QPen(QColor("#00d4ff"), 3))
    painter.setBrush(grad)
    painter.drawEllipse(4, 4, 56, 56)
    painter.end()
    return QIcon(pm)


def build_tray(launcher, cfg):
    tray = QSystemTrayIcon(make_tray_icon())
    menu = QMenu()
    open_action = menu.addAction("Abrir (Ctrl+Espaco)")
    open_action.triggered.connect(launcher.toggle_menu)
    config_action = menu.addAction("Configuracoes")
    config_action.triggered.connect(
        lambda: os.startfile(cfgmod.CONFIG_PATH))
    autostart_action = QAction("Iniciar com o Windows", menu)
    autostart_action.setCheckable(True)
    autostart_action.setChecked(is_autostart())
    autostart_action.toggled.connect(set_autostart)
    menu.addAction(autostart_action)
    quit_action = menu.addAction("Sair")
    quit_action.triggered.connect(QApplication.instance().quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: launcher.toggle_menu()
        if reason == QSystemTrayIcon.DoubleClick else None)
    tray.setToolTip("MeuLauncher - menu rapido")
    tray.show()
    return tray, autostart_action


def register_hotkey(cfg):
    modifiers = cfg["hotkey"].get("modifiers", ["control"])
    key = resolve_key_code(cfg["hotkey"].get("key", "space"))
    mods = 0
    for name in modifiers:
        mods |= MOD_MAP.get(str(name).lower(), 0)
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, mods, key):
        print("Falha ao registrar hotkey (talvez ja esteja em uso).")
    return user32


def main():
    first_run = cfgmod.ensure_defaults()
    cfg = cfgmod.load()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    launcher = Launcher(app, cfg)
    tray, autostart_action = build_tray(launcher, cfg)
    user32 = register_hotkey(cfg)
    hotkey_filter = HotkeyFilter(launcher.toggle_menu)
    app.installNativeEventFilter(hotkey_filter)
    if first_run and not os.environ.get("MEULAUNCHER_SMOKE"):
        reply = QMessageBox.question(
            None, "MeuLauncher",
            "Deseja iniciar o MeuLauncher junto com o Windows?")
        if reply == QMessageBox.Yes:
            set_autostart(True)
            autostart_action.setChecked(True)
    if os.environ.get("MEULAUNCHER_SMOKE"):
        QTimer.singleShot(3000, app.quit)
    app.aboutToQuit.connect(
        lambda: ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID))
    app.exec_()


if __name__ == "__main__":
    main()
