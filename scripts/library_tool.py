"""背景素材库管理。素材库 = 一个文件夹，里面是整理好的背景片段（1920×1080、30fps、无声）+ library.json。
默认位置：<skill>/assets/backgrounds，没有时用共享位置 ~/.math-rap-video/backgrounds；也可以用 --lib 指定，或设置环境变量 MATH_RAP_LIBRARY。

用法:
    python library_tool.py add <视频文件> --id BG27_Rain --roles trap,transition --desc "雨夜窗边的台灯" [--prompt "生成提示词"]
    python library_tool.py tag <片段名> [--roles a,b] [--busy | --quiet]   # 改用途或"安静"标记
    python library_tool.py remove <片段名>      # 从库里删掉一段（连文件）
    python library_tool.py list                 # 按用途列出所有片段（带 * 的是"安静"片段）
    python library_tool.py sheet [输出.jpg]      # 生成总览图 library_overview.jpg（每段一帧，标注名字和用途）
    python library_tool.py check                # 检查文件是否齐全、每种用途是否至少 2 段

add 会自动：去掉上下黑边、放大 6% 裁掉边框、统一成 1920×1080 30fps、去掉声音、压缩。任何来源的视频都可以加
（Flow、可灵、即梦、实拍…），只要是横屏、画面偏暗、没有文字。

"安静"片段（--quiet，默认）：画面暗、没有亮的人脸特写或发光的大块，上面压图形和文字最清楚。
"热闹"片段（--busy）：有亮的人脸特写、强光源或很多细节。分镜里在用途后加 :quiet（如 "demo:quiet"）就只挑安静的。

用途（roles）固定 9 种，对应视频的叙事段落：
    problem 抛问题 | trap 陷阱/苦恼 | reveal 给口诀 | demo 示范计算 | transition 过渡
    hook 口诀大字 | principle 讲原理 | aha 恍然大悟 | outro 收尾
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # 系统编码不支持中文时也不要崩
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROLES = ["problem", "trap", "reveal", "demo", "transition", "hook", "principle", "aha", "outro"]
ROLE_CN = {"problem": "抛问题", "trap": "陷阱/苦恼", "reveal": "给口诀", "demo": "示范计算", "transition": "过渡",
           "hook": "口诀大字", "principle": "讲原理", "aha": "恍然大悟", "outro": "收尾"}
HERE = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("cmd", choices=["add", "tag", "remove", "list", "sheet", "check"])
ap.add_argument("arg", nargs="?")
ap.add_argument("--lib")
ap.add_argument("--id")
ap.add_argument("--roles")
ap.add_argument("--desc", default="")
ap.add_argument("--prompt", default="")
ap.add_argument("--source", default="")
ap.add_argument("--busy", action="store_true")
ap.add_argument("--quiet", action="store_true")
args = ap.parse_args()

from mrv_paths import library_dir  # noqa: E402

LIB = library_dir(args.lib)
LIB.mkdir(parents=True, exist_ok=True)
JS = LIB / "library.json"
data = json.loads(JS.read_text(encoding="utf-8")) if JS.exists() else {"roles": ROLE_CN, "clips": []}


def save():
    data["clips"].sort(key=lambda c: c["id"])
    JS.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def probe_duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return round(float(r.stdout.strip()), 2)


if args.cmd == "add":
    src = Path(args.arg)
    if not src.exists():
        sys.exit(f"找不到 {src}")
    if not args.id or not args.roles:
        sys.exit("add 需要 --id 和 --roles")
    roles = [r.strip() for r in args.roles.split(",")]
    bad = [r for r in roles if r not in ROLES]
    if bad:
        sys.exit(f"不认识的用途 {bad}，可用：{ROLES}")
    # 检测上下黑边（电影宽银幕）
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", "1", "-i", str(src), "-vf", "cropdetect=limit=28:round=2:reset=0",
                        "-frames:v", "60", "-f", "null", "-"], capture_output=True, text=True)
    crops = re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", r.stderr)
    vf = []
    if crops:
        w, h, x, y = map(int, crops[-1])
        r2 = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                             "-of", "csv=p=0", str(src)], capture_output=True, text=True)
        sw, sh = map(int, r2.stdout.strip().split(","))
        if h < sh * 0.97 and h > sh * 0.5 and w > sw * 0.9:  # 只处理上下黑边
            vf.append(f"crop={sw}:{h}:0:{y}")
    vf += ["scale=2036:1146:force_original_aspect_ratio=increase", "crop=1920:1080", "fps=30", "format=yuv420p"]
    out = LIB / f"{args.id}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", ",".join(vf), "-an",
                    "-c:v", "libx264", "-crf", "24", "-preset", "medium", "-movflags", "+faststart", str(out)], check=True)
    data["clips"] = [c for c in data["clips"] if c["id"] != args.id]
    data["clips"].append({"id": args.id, "file": out.name, "roles": roles, "desc": args.desc,
                          "duration": probe_duration(out), "source": args.source, "prompt": args.prompt,
                          "busy": bool(args.busy)})
    save()
    print(f"已加入 {args.id}（{out.stat().st_size / 1e6:.1f} MB，{'已去黑边，' if len(vf) > 4 else ''}用途 {roles}）")

elif args.cmd in ("tag", "remove"):
    clip = next((c for c in data["clips"] if c["id"] == args.arg), None)
    if clip is None:
        sys.exit(f"库里没有 {args.arg}。用 list 查看片段名")
    if args.cmd == "remove":
        (LIB / clip["file"]).unlink(missing_ok=True)
        data["clips"] = [c for c in data["clips"] if c["id"] != args.arg]
        save()
        print(f"已删除 {args.arg}，还剩 {len(data['clips'])} 段")
    else:
        if args.roles:
            roles = [r.strip() for r in args.roles.split(",")]
            bad = [r for r in roles if r not in ROLES]
            if bad:
                sys.exit(f"不认识的用途 {bad}，可用：{ROLES}")
            clip["roles"] = roles
        if args.busy or args.quiet:
            clip["busy"] = bool(args.busy)
        save()
        print(f"{clip['id']}：用途 {clip['roles']}，{'热闹' if clip.get('busy') else '安静'}")

elif args.cmd == "list":
    for role in ROLES:
        cs = [c for c in data["clips"] if role in c["roles"]]
        nq = sum(not c.get("busy") for c in cs)
        print(f"{role:11s}{ROLE_CN[role]:　<6s} {len(cs)} 段（安静 {nq}）：" +
              "、".join(c["id"] + ("" if c.get("busy") else "*") for c in cs))
    print(f"共 {len(data['clips'])} 段，{sum((LIB / c['file']).stat().st_size for c in data['clips']) / 1e6:.0f} MB，位置 {LIB}")

elif args.cmd == "check":
    ok = True
    for c in data["clips"]:
        if not (LIB / c["file"]).exists():
            print("缺文件：", c["file"])
            ok = False
    for role in ROLES:
        n = sum(role in c["roles"] for c in data["clips"])
        if n < 2:
            print(f"用途 {role}（{ROLE_CN[role]}）只有 {n} 段，建议至少 2 段")
            ok = False
    print("素材库正常" if ok else "素材库有问题", f"（{len(data['clips'])} 段）")
    sys.exit(0 if ok else 1)

elif args.cmd == "sheet":
    from PIL import Image, ImageDraw, ImageFont

    out = Path(args.arg or LIB / "library_overview.jpg")
    font = None
    for f in ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf", "/System/Library/Fonts/PingFang.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]:
        if Path(f).exists():
            font = ImageFont.truetype(f, 20)
            break
    cols, tw, th = 4, 480, 270
    clips = sorted(data["clips"], key=lambda c: c["id"])
    sheet = Image.new("RGB", (cols * tw, ((len(clips) + cols - 1) // cols) * (th + 54)), (18, 18, 22))
    tmp = LIB / "_frame.jpg"
    for n, c in enumerate(clips):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(c["duration"] / 2), "-i", str(LIB / c["file"]),
                        "-frames:v", "1", "-vf", f"scale={tw}:{th}", str(tmp)], check=True)
        x, y = (n % cols) * tw, (n // cols) * (th + 54)
        sheet.paste(Image.open(tmp), (x, y))
        d = ImageDraw.Draw(sheet)
        d.text((x + 8, y + th + 4), c["id"], fill=(255, 216, 74), font=font)
        d.text((x + 8, y + th + 28), " ".join(ROLE_CN[r] for r in c["roles"]) + ("" if c.get("busy") else "  [安静]"),
               fill=(200, 200, 210), font=font)
    tmp.unlink(missing_ok=True)
    sheet.save(out, quality=88)
    print(out)
