"""画风：长相和题目分开。

一个画风 = 一个文件夹：styles/<名字>/style.json（只放值）+ README.md（适合什么题）+ preview.jpg（样张）。
作品的 storyboard.json 写 "style": "<名字>" 就换上；想单独改某一项，在 storyboard.json 里写同名的键覆盖
（colors / fonts / banner / subtitles / formula / glow / backgrounds）。

画风从这几个地方找（前面的优先）：
  1. 作品目录里的相对路径（"style": "我的画风/style.json" 或一个文件夹）
  2. ~/.math-rap-video/styles/<名字>/      你自己做的画风，各家 AI 工具共用
  3. <skill>/styles/<名字>/                 skill 自带的画风

颜色用语义名：text 正文、primary 主图形、primary_dark / primary_light 主色深浅、highlight 正在讲的、
result 结果数字、accent 箭头和强调、ok 对的、muted 次要、line 细线、stroke 字的描边。
旧名字（white blue blue_dark blue_light red yellow orange green gray）照样能用，自动对到语义名上。
"""
import json
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
USER_STYLES = Path.home() / ".math-rap-video" / "styles"
DEFAULT = "cinema"

ALIASES = {
    "white": "text", "blue": "primary", "blue_dark": "primary_dark", "blue_light": "primary_light",
    "red": "highlight", "yellow": "result", "orange": "accent", "green": "ok", "gray": "muted",
}

BASE = {
    "id": "base",
    "palette": {
        "text": "#FFFFFF", "primary": "#4C8DFF", "primary_dark": "#285CC8", "primary_light": "#82B9FF",
        "highlight": "#EC546A", "result": "#FFD84A", "accent": "#FF6030", "ok": "#5CD68C",
        "muted": "#9696A0", "line": "#E6ECFF", "stroke": "#000000",
    },
    "fonts": {"heavy": [], "subtitle": []},
    "banner": {"y": 78, "size": 84, "color": "text", "stroke": 3},
    "formula": {"y": 830},
    "subtitles": {"y": 1010, "size": 64, "color": "text", "box": True, "box_color": "#000000", "box_alpha": 165,
                  "stroke": 0, "radius": 0},
    "glow": None,
    "backgrounds": {"source": "library",
                    "grade": "eq=brightness=-0.16:saturation=0.65:contrast=1.05,vignette=PI/3.2"},
}


def rgba(v, alpha=255):
    """'#RRGGBB' / '#RRGGBBAA' / [r,g,b] / [r,g,b,a] → (r,g,b,a)。"""
    if isinstance(v, str):
        s = v.lstrip("#")
        if len(s) == 6:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)
        if len(s) == 8:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
        raise ValueError(f"颜色写法不对：{v}（写 #RRGGBB）")
    v = tuple(int(x) for x in v)
    return v if len(v) == 4 else v + (alpha,)


def merge(a, b):
    """b 覆盖 a；两边都是字典的键往下一层合并。"""
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _dir_of(p):
    p = Path(p)
    if p.is_file():
        return p.parent, p
    if (p / "style.json").exists():
        return p, p / "style.json"
    return None, None


def find_style(name=None, work=None):
    """返回 (画风文件夹, style.json 路径)；找不到返回 (None, None)。"""
    name = name or DEFAULT
    if work is not None:
        d, f = _dir_of(Path(work) / name)
        if f:
            return d, f
    if Path(name).is_absolute():
        return _dir_of(name)
    for root in (USER_STYLES, SKILL / "styles"):
        d, f = _dir_of(root / name)
        if f:
            return d, f
    return None, None


def list_styles():
    seen, out = set(), []
    for root in (USER_STYLES, SKILL / "styles"):
        if not root.exists():
            continue
        for d in sorted(root.iterdir()):
            f = d / "style.json"
            if f.exists() and d.name not in seen:
                seen.add(d.name)
                try:
                    j = json.loads(f.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    j = {"name": f"（style.json 写错了：{e}）"}
                out.append({"id": d.name, "name": j.get("name", d.name), "desc": j.get("desc", ""),
                            "dir": str(d), "mine": root == USER_STYLES})
    return out


def load_style(name=None, work=None):
    """读画风，和内置默认值合并；字体路径换成绝对路径。找不到时报出可用的画风。"""
    d, f = find_style(name, work)
    if f is None:
        have = "、".join(s["id"] for s in list_styles()) or "（一个都没有）"
        raise SystemExit(f"错误：找不到画风「{name}」。可用的：{have}。用 mrv.py styles 看说明")
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"错误：{f} 不是合法的 JSON：{e}")
    st = merge(BASE, j)
    for k in ("heavy", "subtitle"):
        st["fonts"][k] = [str(Path(p).expanduser()) if p.startswith("~") or Path(p).is_absolute() else str((d / p).resolve())
                          for p in st["fonts"].get(k, [])]
    st["_dir"] = str(d)
    st["id"] = j.get("id", d.name)
    return st


def palette_colors(st):
    """画风的色板 → 引擎用的颜色表：语义名 + 旧名字。"""
    pal = {k: rgba(v) for k, v in st["palette"].items()}
    out = dict(pal)
    for old, sem in ALIASES.items():
        if sem in pal:
            out[old] = pal[sem]
    return out
