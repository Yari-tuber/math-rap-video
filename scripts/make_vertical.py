"""把横屏成片做成竖屏版（1080×1920）：成片放在中间，上方大标题，下方一行小字，背景是成片自身的模糊放大。
适合抖音、快手、视频号等竖屏平台；画面内容不变，所以不用重新渲染。

用法:
    python make_vertical.py <作品目录> [--title "数线段：八个字秒出答案"] [--sub "小学四年级 · 数学思维"] [--in 成片.mp4]
标题和小字也可以写在 storyboard.json 里：  "vertical": {"title": "…", "sub": "…"}
都不写时，标题取歌词文件第一行的 # 标题，小字不显示（口诀已经在画面里了；小字适合写"适合几年级""系列第几集"之类）。
输出：成片_竖屏.mp4
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

ap = argparse.ArgumentParser()
ap.add_argument("work")
ap.add_argument("--title")
ap.add_argument("--sub")
ap.add_argument("--in", dest="src", default="成片.mp4")
args = ap.parse_args()

WORK = Path(args.work).resolve()
HERE = Path(__file__).resolve().parent
src = WORK / args.src
if not src.exists():
    sys.exit(f"找不到 {src}：先用 build_video.py 出横屏成片")
SB = json.loads((WORK / "storyboard.json").read_text(encoding="utf-8")) if (WORK / "storyboard.json").exists() else {}
vcfg = SB.get("vertical", {})

title = args.title or vcfg.get("title")
if not title:
    lf = next((WORK / n for n in ("lyrics.md", "歌词.md") if (WORK / n).exists()), None)
    if lf:
        m = re.search(r"^#\s+(.+)$", lf.read_text(encoding="utf-8-sig"), re.M)
        title = re.sub(r"[（(].*?[)）]", "", m.group(1)).strip() if m else None
sub = args.sub or vcfg.get("sub")
title = title or ""
sub = sub or ""

# 字体：问引擎用的是哪个，保持和成片一致
font_path = None
r = subprocess.run([sys.executable, str(HERE / "overlay_engine.py"), str(WORK), "info"], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
if r.returncode == 0:
    font_path = json.loads(r.stdout).get("font_heavy")
if not font_path:
    for c in ["C:/Windows/Fonts/NotoSansSC-VF.ttf", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf",
              "/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
              "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"]:
        if Path(c).exists():
            font_path = c
            break
if not font_path:
    sys.exit("找不到中文字体：在 storyboard.json 里写 fonts，或把字体放进 skill 的 assets/fonts/")

W, H = 1080, 1920
VID_H = 608            # 1080×608 的 16:9 画面
VID_Y = (H - VID_H) // 2


def font(size):
    f = ImageFont.truetype(font_path, size)
    try:
        f.set_variation_by_axes([900])
    except Exception:  # noqa: BLE001
        pass
    return f


def wrap(text, f, max_w):
    """按宽度折行；优先在标点或空格后面断。"""
    parts = re.split(r"(?<=[，,：:？?！!、 ])", text)
    lines, cur = [], ""
    for p in parts:
        if f.getlength(cur + p) <= max_w or not cur:
            cur += p
        else:
            lines.append(cur.strip())
            cur = p
    if cur.strip():
        lines.append(cur.strip())
    out = []
    for ln in lines:  # 单段仍然太长就按字硬断
        while f.getlength(ln) > max_w:
            k = len(ln)
            while k > 1 and f.getlength(ln[:k]) > max_w:
                k -= 1
            out.append(ln[:k])
            ln = ln[k:]
        out.append(ln)
    return out


def draw_block(d, text, size, color, y_bottom=None, y_top=None, stroke=5):
    f = font(size)
    lines = wrap(text, f, W - 120)
    lh = int(size * 1.28)
    total = lh * len(lines)
    y = (y_bottom - total) if y_bottom is not None else y_top
    for ln in lines:
        w = f.getlength(ln)
        d.text(((W - w) / 2, y), ln, font=f, fill=color, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        y += lh


ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(ov)
if title:
    draw_block(d, title, 92, (255, 216, 74, 255), y_bottom=VID_Y - 70)
if sub:
    draw_block(d, sub, 58, (255, 255, 255, 255), y_top=VID_Y + VID_H + 70, stroke=4)
ov_path = WORK / "_vertical_overlay.png"
ov.save(ov_path)

out = WORK / "成片_竖屏.mp4"
fc = (f"[0:v]split=2[a][b];"
      f"[a]scale=-2:{H},crop={W}:{H},boxblur=40:8,eq=brightness=-0.32:saturation=0.8[bg];"
      f"[b]scale={W}:{VID_H}[fg];[bg][fg]overlay=0:{VID_Y}[v1];[v1][1:v]overlay=0:0,format=yuv420p[v]")
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-i", str(ov_path), "-filter_complex", fc,
                "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-c:a", "copy",
                "-movflags", "+faststart", str(out)], check=True)
ov_path.unlink(missing_ok=True)
print("竖屏版完成", out)
print(f"标题：{title or '（无）'}　小字：{sub or '（无）'}")
