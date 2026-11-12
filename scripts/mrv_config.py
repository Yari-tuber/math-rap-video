"""这台电脑上的设置：~/.math-rap-video/config.json（各家 AI 工具共用一份）。

    {
      "python": "装了 torch + transformers 的 Python（逐字对齐用；不写就用运行 mrv.py 的这个）",
      "demucs_python": "装了 demucs 的 Python（分人声用；不写就和上面同一个）",
      "aligner_model": "对齐模型：Hugging Face 名字或本地文件夹，默认 Qwen/Qwen3-ForcedAligner-0.6B-hf",
      "style": "默认画风",
      "intro_bars": 2
    }

音乐模型的密钥单独存在 ~/.math-rap-video/keys.json（只在这台电脑上，不进作品目录，不打印）。
也可以用环境变量：ELEVENLABS_API_KEY、MUREKA_API_KEY……（<平台大写>_API_KEY）。
"""
import json
import os
from pathlib import Path

HOME = Path.home() / ".math-rap-video"
CONFIG = HOME / "config.json"
KEYS = HOME / "keys.json"


def load():
    if CONFIG.exists():
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def get(key, default=None):
    return load().get(key, default)


def set_(key, value):
    HOME.mkdir(parents=True, exist_ok=True)
    c = load()
    if value is None:
        c.pop(key, None)
    else:
        c[key] = value
    CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def heavy_python():
    """对齐、分离人声用的 Python。"""
    import sys
    return os.environ.get("MRV_PYTHON") or get("python") or sys.executable


def demucs_python():
    """分人声用的 Python（没单独设就和对齐用同一个）。"""
    return os.environ.get("MRV_DEMUCS_PYTHON") or get("demucs_python") or heavy_python()


def get_key(provider):
    env = os.environ.get(f"{provider.upper()}_API_KEY")
    if env:
        return env.strip()
    if KEYS.exists():
        try:
            v = json.loads(KEYS.read_text(encoding="utf-8")).get(provider)
            if v:
                return v.strip()
        except json.JSONDecodeError:
            pass
    return None


def save_key(provider, key):
    HOME.mkdir(parents=True, exist_ok=True)
    d = {}
    if KEYS.exists():
        try:
            d = json.loads(KEYS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            d = {}
    d[provider] = key.strip()
    KEYS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        os.chmod(KEYS, 0o600)
    except OSError:
        pass
