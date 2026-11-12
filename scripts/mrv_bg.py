"""背景的四种来源（画风的 backgrounds 写默认值，作品的 storyboard.json 可以覆盖）：

    {"source": "library", "plan": [["T0", "problem"], ["L(3)", "trap"], …]}   自带素材库，按用途挑（原来那套）
    {"source": "folder",  "path": "D:/我的素材"}                              自己的视频文件夹，轮流用；不写 plan 就每 4 句换一段
    {"source": "image",   "path": "bg.jpg", "motion": "slow-zoom"}            一张图，慢慢推近（motion: none 不动）
    {"source": "color",   "color": "#0B1A2C", "color2": "#040A14", "texture": "grid"}
                                                                               纯色渐变，texture 可选 grid 网格 / chalk 黑板 / noise 颗粒 / none
共同的键：grade（ffmpeg 调色滤镜，整片统一压暗、降饱和、暗角）。
"""
import math
import random
import subprocess
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi"}


def _rgb(v):
    s = v.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def color_still(spec, size=(1920, 1080)):
    """纯色 / 渐变 / 纹理背景，返回 RGBA 图。"""
    from PIL import Image, ImageDraw, ImageFilter
    w, h = size
    c1 = _rgb(spec.get("color", "#14161C"))
    c2 = _rgb(spec.get("color2", spec.get("color", "#14161C")))
    im = Image.new("RGB", size, c1)
    d = ImageDraw.Draw(im)
    for y in range(h):          # 上浅下深的竖向渐变
        f = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(c1[i] + (c2[i] - c1[i]) * f) for i in range(3)))
    tex = spec.get("texture", "none")
    rng = random.Random(spec.get("seed", 7))
    if tex == "grid":
        lay = Image.new("RGBA", size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lay)
        step = int(spec.get("grid", 64))
        line = _rgb(spec.get("grid_color", "#5FB4FF"))
        for k, x in enumerate(range(0, w + 1, step)):
            ld.line([(x, 0), (x, h)], fill=line + (34 if k % 4 == 0 else 14,), width=1)
        for k, y in enumerate(range(0, h + 1, step)):
            ld.line([(0, y), (w, y)], fill=line + (34 if k % 4 == 0 else 14,), width=1)
        glow = Image.new("RGBA", size, (0, 0, 0, 0))   # 中间一团很淡的光，网格不死板
        ImageDraw.Draw(glow).ellipse([w * 0.18, h * 0.05, w * 0.82, h * 0.95], fill=line + (26,))
        glow = glow.filter(ImageFilter.GaussianBlur(160))
        im = im.convert("RGBA")
        im.alpha_composite(glow)
        im.alpha_composite(lay)
    elif tex in ("chalk", "noise"):
        im = im.convert("RGBA")
        small = Image.new("L", (w // 16, h // 16))
        small.putdata([rng.randint(0, 255) for _ in range(small.width * small.height)])
        smudge = small.resize(size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(28))
        tint = Image.new("RGBA", size, (255, 255, 255, 0))
        tint.putalpha(smudge.point(lambda v: int(max(0, v - 120) * (0.10 if tex == "chalk" else 0.06))))
        im.alpha_composite(tint)
        if tex == "chalk":       # 擦过的粉笔痕：几道很淡的弧
            lay = Image.new("RGBA", size, (0, 0, 0, 0))
            ld = ImageDraw.Draw(lay)
            for _ in range(14):
                cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(120, 420)
                a0 = rng.uniform(0, 360)
                ld.arc([cx - r, cy - r * 0.45, cx + r, cy + r * 0.45], a0, a0 + rng.uniform(40, 120),
                       fill=(235, 240, 230, rng.randint(10, 20)), width=rng.randint(18, 46))
            im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(10)))
        grain = Image.new("L", size)
        grain.putdata([rng.randint(0, 255) for _ in range(w * h)] if w * h <= 2_100_000 else [128] * (w * h))
        g = Image.new("RGBA", size, (255, 255, 255, 0))
        g.putalpha(grain.point(lambda v: 6 if v > 200 else 0))
        im.alpha_composite(g)
    return im.convert("RGBA")


def folder_clips(folder):
    """把一个视频文件夹变成素材列表（不改动那个文件夹）。"""
    folder = Path(folder)
    if not folder.is_dir():
        raise SystemExit(f"错误：背景文件夹不存在：{folder}")
    vids = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not vids:
        raise SystemExit(f"错误：{folder} 里没有视频文件（{'、'.join(sorted(VIDEO_EXT))}）")
    out = []
    for p in vids:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True)
        try:
            dur = float(r.stdout.strip())
        except ValueError:
            continue
        out.append({"id": p.stem, "file": str(p), "duration": dur, "roles": []})
    return out


def still_filter(dur, motion="slow-zoom", fps=30):
    """一张静止图做成视频时的滤镜：慢慢推近 4%（motion=none 不动）。"""
    if motion == "none":
        return f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps={fps}"
    return (f"scale=2112:1188:force_original_aspect_ratio=increase,crop=2112:1188,"
            f"scale=w='trunc(1920*(1+0.04*t/{max(dur, 1):.3f})/2)*2':h=-2:eval=frame,crop=1920:1080,fps={fps}")
