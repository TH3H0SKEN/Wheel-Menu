import ctypes
import subprocess


def open_settings():
    subprocess.Popen("start ms-settings:", shell=True)


def open_control_panel():
    subprocess.Popen("control", shell=True)


def open_task_manager():
    subprocess.Popen("taskmgr", shell=True)


def shutdown_pc():
    subprocess.Popen(["shutdown", "/s", "/t", "0"])


def restart_pc():
    subprocess.Popen(["shutdown", "/r", "/t", "0"])


def logoff_pc():
    subprocess.Popen(["shutdown", "/l"])


def suspend_pc():
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])


def lock_pc():
    ctypes.windll.user32.LockWorkStation()
