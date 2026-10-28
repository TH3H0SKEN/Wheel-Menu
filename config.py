import json
import os

APP_NAME = "MeuLauncher"
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "hotkey": {"modifiers": ["control"], "key": "space"},
    "sectors": 8,
    "radius_inner": 95,
    "radius_outer": 195,
    "subradius_inner": 205,
    "subradius_outer": 285,
    "alpha": 1.0,
    "fade_in_ms": 120,
    "fade_out_ms": 100,
    "hover_delay_ms": 200,
    "colors": {
        "fundo_alpha": 175,
        "cor_fundo": "#0a0c10",
        "cor_borda": "#00d4ff",
        "cor_borda_fim": "#0066ff",
        "cor_hover_inicio": "#2563eb",
        "cor_hover_fim": "#7c3aed",
        "cor_hover_alpha": 205,
        "cor_texto": "#ffffff",
        "cor_texto_alpha": 230,
        "cor_glow": "#00d4ff",
        "cor_setor_inativo": "#ffffff",
        "cor_setor_inativo_alpha": 15,
        "espessura_borda": 2
    },
    "favorites": [
        {"name": "Explorador de Arquivos", "path": "explorer.exe"},
        {"name": "Calculadora", "path": "calc.exe"},
        {"name": "Bloco de Notas", "path": "notepad.exe"},
        {"name": "Prompt de Comando", "path": "cmd.exe"}
    ]
}


def _merge(defaults, user):
    result = dict(defaults)
    if not isinstance(user, dict):
        return result
    for key, value in user.items():
        if key in defaults and isinstance(defaults[key], dict) and isinstance(value, dict):
            result[key] = _merge(defaults[key], value)
        else:
            result[key] = value
    return result


def load():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = _merge(DEFAULT_CONFIG, json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return cfg


def save(cfg):
    os.makedirs(APP_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def ensure_defaults():
    if not os.path.exists(CONFIG_PATH):
        save(DEFAULT_CONFIG)
        return True
    return False
