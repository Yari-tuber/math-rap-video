"""环境自检：开始制作前运行一次，确认该装的都装了。
用法: python check_env.py
全部必需项通过时退出码为 0。
"""
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
ok = True


def line(good, name, detail="", required=True):
    global ok
    mark = "[OK]  " if good else ("[缺少]" if required else "[可选]")
    print(f"{mark} {name}" + (f"：{detail}" if detail else ""))
    if not good and required:
        ok = False


v = sys.version_info
line(v >= (3, 10), f"Python {v.major}.{v.minor}", "" if v >= (3, 10) else "需要 3.10 或更高")

for mod, pip, req, why in [
    ("PIL", "pillow", True, "画图"),
    ("numpy", "numpy", True, "计算"),
    ("librosa", "librosa", True, "检测速度和节拍（纯配音加 --no-beat 时可以没有）"),
    ("pypinyin", "pypinyin", False, "字幕对齐按拼音匹配，更耐同音字；歌词体检查押韵"),
    ("demucs", "demucs", False, "prepare_audio --deep 分离人声做深入比较"),
]:
    try:
        importlib.import_module(mod)
        line(True, f"Python 库 {pip}")
    except Exception:  # noqa: BLE001
        line(False, f"Python 库 {pip}", f"pip install {pip}（用途：{why}）", req)

for exe in ("ffmpeg", "ffprobe"):
    p = shutil.which(exe)
    if p:
        r = subprocess.run([exe, "-version"], capture_output=True, text=True, errors="replace")
        line(True, exe, r.stdout.splitlines()[0][:60] if r.stdout else p)
    else:
        line(False, exe, "没有在 PATH 里找到。到 ffmpeg.org 下载并加入 PATH")

bundled = sorted((HERE.parent / "assets" / "fonts").glob("*.[to]t[fc]")) if (HERE.parent / "assets" / "fonts").exists() else []
cands = [str(p) for p in bundled] + [
    "C:/Windows/Fonts/NotoSansSC-VF.ttf", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]
found = next((c for c in cands if Path(c).exists()), None)
line(bool(found), "中文粗体字体", found or "没找到。把一个中文粗体字体文件（.ttf/.otf/.ttc）放进 skill 的 assets/fonts/，"
     "或在 storyboard.json 里写 fonts")

from mrv_paths import library_dir  # noqa: E402

lib = library_dir()
if (lib / "library.json").exists():
    import json

    clips = json.loads((lib / "library.json").read_text(encoding="utf-8"))["clips"]
    missing = [c["file"] for c in clips if not (lib / c["file"]).exists()]
    line(not missing, f"背景素材库（{len(clips)} 段）", str(lib) if not missing else f"缺 {len(missing)} 个文件，如 {missing[0]}")
else:
    line(False, "背景素材库", "还没有。拿到素材库压缩包后运行：python install.py --library <压缩包.zip>"
         f"（或手动解压到 {lib}）")

print("\n环境就绪，可以开始。" if ok else "\n有必需项缺失，先按上面的提示处理。")
sys.exit(0 if ok else 1)
