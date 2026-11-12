"""合成成片：从素材库按分镜挑背景并剪好 → 叠加层 → 配上音频。参数全部读作品目录的 storyboard.json 和 timing.json。
用法:
    python build_video.py <作品目录> bg              # 挑背景并拼接 → 成片_背景.mp4（同时写 背景分配.json）
    python build_video.py <作品目录> final           # 叠加层 + 音频 → 成片.mp4（全片约 8–10 分钟）
    python build_video.py <作品目录> final 20 30     # 只出音频 20–30 秒的片段 → 成片_片段.mp4
    python build_video.py <作品目录> sheet           # 从成片每句抽一帧 → 成片_总览.jpg
    python build_video.py <作品目录> all             # 先 check，再 bg + final + sheet（一条命令出片）

背景从哪来由画风决定（styles/<画风>/style.json 的 backgrounds），storyboard.json 的 backgrounds 可以覆盖：
    "source": "library"（自带素材库，按用途挑）/ "folder"（"path": 自己的视频文件夹）/ "image"（"path": 一张图）/
              "color"（"color" "color2" "texture": grid / chalk / noise）。详见 mrv_bg.py。
source 是 library 时：
    "plan": [["T0", "problem"], ["L(3)", "trap"], ["L(9)", "demo:quiet"], ["L(5)", "BG01_Chalkboard"], …]
        每项 [切入时间, 用途或片段名]；切点自动提前 lead 秒（默认 0.1），落在小节线上。
        中间有题目图形的段落会自动只挑"安静"片段（没有亮的人脸特写）。
        用途后加 :quiet 强制只挑安静片段；加 :any 表示这一段不限制；"auto_quiet": false 关掉自动判断。
    "library": 素材库目录（可省略：环境变量 MATH_RAP_LIBRARY → <skill>/assets/backgrounds → ~/.math-rap-video/backgrounds）
    "seed": 换个数字就换一套随机挑选；"grade": 调色滤镜；"lead": 切点提前量
"""
import json
import os
import random
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # 系统编码不支持中文时也不要崩
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0)
WORK = Path(sys.argv[1]).resolve()
STEP = sys.argv[2] if len(sys.argv) > 2 else "all"
if STEP not in ("bg", "final", "sheet", "all"):
    sys.exit(f"不认识的步骤 {STEP}，可用：bg / final / sheet / all")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mrv_bg import color_still, folder_clips, still_filter  # noqa: E402
from mrv_style import load_style, merge  # noqa: E402

ENGINE = str(HERE / "overlay_engine.py")
SB = json.loads((WORK / "storyboard.json").read_text(encoding="utf-8"))
STYLE = load_style(SB.get("style"), WORK)
BGC = merge(STYLE.get("backgrounds", {}), SB.get("backgrounds", {}))
SRC = BGC.get("source", "library")
if SRC == "library":         # 没下素材库也别卡住：先用暗色纯色底出片，提示怎么装
    from mrv_paths import library_dir as _ld
    if not (_ld(BGC.get("library"), WORK) / "library.json").exists():
        print("提示：没找到背景素材库，这次先用暗色纯色底出片。想要电影镜头背景：python "
              f"\"{HERE / 'install.py'}\" --get-library（97 MB），装好重跑 render", file=sys.stderr)
        SRC = "color"
        BGC = merge({"color": "#141A26", "color2": "#06080D", "texture": "noise"}, BGC)
if SRC not in ("library", "folder", "image", "color"):
    sys.exit(f"backgrounds.source 只能是 library / folder / image / color，现在是「{SRC}」")
GRADE = BGC.get("grade", "eq=brightness=-0.16:saturation=0.65:contrast=1.05,vignette=PI/3.2")


def engine_info(exprs=()):
    r = subprocess.run([sys.executable, ENGINE, str(WORK), "info", *exprs], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.exit(r.stderr.strip() or "读取分镜失败")
    return json.loads(r.stdout)


plan = BGC.get("plan", []) if SRC in ("library", "folder") else []
INFO = engine_info([str(p[0]) for p in plan])
T0, T_END, FPS = INFO["t0"], INFO["t_end"], INFO["fps"]
if SRC == "folder" and not plan:      # 自己的视频文件夹、没写切换计划：每 4 句换一段
    plan = [["T0", "any"]] + [[f"L({i})", "any"] for i in range(5, len(INFO["lines"]) + 1, 4)]
    INFO = engine_info([str(p[0]) for p in plan])
bg_path = WORK / "成片_背景.mp4"


def probe_duration(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def resolve_backgrounds():
    from mrv_paths import NOT_FOUND_HINT, library_dir

    if SRC == "folder":
        fp = Path(BGC.get("path", ""))
        lib_dir = fp if fp.is_absolute() else WORK / fp
        clips = folder_clips(lib_dir)
        for c in clips:           # 自己的素材没有用途标签：任何用途都能用
            c["roles"] = ["any"] + [str(p[1]).partition(":")[0] for p in plan]
    else:
        lib_dir = library_dir(BGC.get("library"), WORK)
        lj = lib_dir / "library.json"
        if not lj.exists():
            sys.exit(NOT_FOUND_HINT + f"（当前查找的位置：{lib_dir}）。不想下素材库：storyboard.json 里写 "
                     '"backgrounds": {"source": "color"}，或换一个画风（mrv.py styles）')
        clips = json.loads(lj.read_text(encoding="utf-8"))["clips"]
    by_id = {c["id"]: c for c in clips}
    if not plan:
        sys.exit("storyboard.json 里没有 backgrounds.plan")
    lead = BGC.get("lead", 0.1)
    rng = random.Random(BGC.get("seed", 1))
    used = {}
    segs = []
    times = [max(T0, INFO["values"][str(p[0])] - lead) for p in plan]
    times[0] = T0
    for k in range(1, len(times)):
        if times[k] <= times[k - 1] + 0.5:
            sys.exit(f"背景切换点要递增且间隔大于 0.5 秒：第 {k + 1} 项 {plan[k][0]} = {times[k]:.2f}")
    # 每段背景取 3 个时间点，问引擎那时题目图形占多大画面
    ends = times[1:] + [T_END]
    probes = [f"{times[k] + (ends[k] - times[k]) * f:.3f}" for k in range(len(plan)) for f in (0.3, 0.6, 0.9)]
    r = subprocess.run([sys.executable, ENGINE, str(WORK), "cover", *probes], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    try:
        cov = json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        cov = [0.0] * len(probes)
    has_graphics = [sum(1 for v in cov[3 * k:3 * k + 3] if v >= 0.03) >= 2 for k in range(len(plan))]
    auto_note = {}
    for k, (expr, want) in enumerate(plan):
        if want in by_id:
            c = by_id[want]
        elif (WORK / want).is_file() or Path(want).is_file():
            p = (WORK / want) if (WORK / want).is_file() else Path(want)
            c = {"id": p.stem, "file": str(p), "duration": probe_duration(p), "roles": []}
        else:
            role, _, mod = want.partition(":")
            if mod not in ("", "quiet", "any"):
                sys.exit(f"背景计划第 {k + 1} 项「{want}」：用途后面只能加 :quiet 或 :any")
            cands = [c for c in clips if role in c["roles"]]
            if not cands:
                sys.exit(f"素材库里没有用途为「{role}」的片段，也没有叫这个名字的片段。运行 library_tool.py list 查看")
            prev = segs[-1]["id"] if segs else None
            # 这一段中间有题目图形时，自动只挑"安静"片段（没有亮的人脸特写），免得人脸压在图形后面
            auto = mod == "" and BGC.get("auto_quiet", True) and has_graphics[k]
            if mod == "quiet" or auto:
                q = [c for c in cands if not c.get("busy") and c["id"] != prev]
                if not q:      # 这种用途没有（别的）安静片段：从整个素材库的安静片段里借
                    q = [c for c in clips if not c.get("busy") and c["id"] != prev]
                if q:
                    cands = q
                    if auto:
                        auto_note[k] = True
                else:
                    print(f"  提示：素材库里没有安静片段，这一段照常挑", file=sys.stderr)
            least = min(used.get(c["id"], 0) for c in cands if c["id"] != prev) if len(cands) > 1 else 0
            pool = [c for c in cands if used.get(c["id"], 0) == least and c["id"] != prev] or cands
            c = rng.choice(sorted(pool, key=lambda c: c["id"]))
        n = used.get(c["id"], 0)
        used[c["id"]] = n + 1
        end = times[k + 1] if k + 1 < len(times) else T_END
        dur = end - times[k]
        fp = Path(c["file"])
        fp = fp if fp.is_absolute() else lib_dir / fp
        # 同一段第二次用时，从后半段取，画面不重复
        off = 0.0 if n == 0 else max(0.0, min(c["duration"] - dur, c["duration"] * 0.35))
        segs.append({"at": round(times[k], 3), "dur": round(dur, 3), "id": c["id"],
                     "want": want + ("（有图形，自动选安静片段）" if auto_note.get(k) else ""),
                     "file": str(fp), "offset": round(off, 2), "clip_len": c["duration"]})
    (WORK / "背景分配.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
    return segs


if STEP == "all":   # 一条命令出片时先体检，有问题就不往下花十分钟
    r = subprocess.run([sys.executable, ENGINE, str(WORK), "check"])
    if r.returncode != 0:
        sys.exit("检查没有通过，先按上面的提示改 storyboard.json / graphics.py，再重新运行")

if STEP in ("bg", "all") and SRC in ("image", "color"):
    dur = T_END - T0
    if SRC == "color":
        still = WORK / "_背景.png"
        color_still(BGC).convert("RGB").save(still)
        print(f"  背景：纯色{('（' + BGC['texture'] + '）') if BGC.get('texture', 'none') != 'none' else ''} {BGC.get('color')}")
    else:
        still = Path(BGC.get("path", ""))
        still = still if still.is_absolute() else WORK / still
        if not still.is_file():
            sys.exit(f"backgrounds.path 指向的图片不存在：{still}")
        print(f"  背景：一张图 {still.name}（{BGC.get('motion', 'slow-zoom')}）")
    vf = still_filter(dur, BGC.get("motion", "slow-zoom"), FPS) + f",{GRADE},format=yuv420p"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", str(still), "-t", f"{dur:.3f}",
                    "-vf", vf, "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-an", str(bg_path)], check=True)
    (WORK / "背景分配.json").write_text(json.dumps([{"at": T0, "dur": round(dur, 3), "source": SRC,
                                                    "file": str(still)}], ensure_ascii=False, indent=1), encoding="utf-8")
    print("背景完成", bg_path)
elif STEP in ("bg", "all"):
    segs = resolve_backgrounds()
    inputs, filters = [], []
    for k, s in enumerate(segs):
        avail = s["clip_len"] - s["offset"] - 0.05
        stretch = max(1.0, s["dur"] / avail)  # 素材不够长就放慢
        note = f"（放慢 {stretch:.2f} 倍）" if stretch > 1.01 else ""
        print(f"  {s['at']:6.2f}s  {s['dur']:5.2f}s  {s['id']:22s} ← {s['want']}{note}")
        if stretch > 1.3:
            print(f"    注意：这段背景要撑 {s['dur']:.1f} 秒，放慢较多；可在 plan 里中间再加一个切换点", file=sys.stderr)
        inputs += ["-i", s["file"]]
        filters.append(
            f"[{k}:v]trim=start={s['offset']}:duration={min(avail, s['dur']):.3f},setpts=(PTS-STARTPTS)*{stretch:.4f},"
            f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,{GRADE},fps={FPS},format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration=1,trim=duration={s['dur']:.3f},setpts=PTS-STARTPTS[v{k}]")
    fc = ";".join(filters) + ";" + "".join(f"[v{k}]" for k in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[out]"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[out]",
                    "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-an", str(bg_path)], check=True)
    print("背景完成", bg_path)

if STEP in ("final", "all"):
    if not bg_path.exists():
        sys.exit("还没有 成片_背景.mp4，先运行 bg")
    a = float(sys.argv[3]) if len(sys.argv) > 3 else T0
    b = float(sys.argv[4]) if len(sys.argv) > 4 else T_END
    full = (a, b) == (T0, T_END)
    out = WORK / ("成片.mp4" if full else "成片_片段.mp4")
    render = subprocess.Popen([sys.executable, ENGINE, str(WORK), "raw", str(a), str(b)], stdout=subprocess.PIPE)
    ff = subprocess.Popen([
        "ffmpeg", "-loglevel", "error", "-y",
        "-ss", f"{a - T0:.3f}", "-t", f"{b - a:.3f}", "-i", str(bg_path),
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1920x1080", "-r", str(FPS), "-i", "-",
        "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(WORK / INFO["song"]),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto:eof_action=pass,format=yuv420p[v];"
                           f"[2:a]afade=t=out:st={max(0, b - a - 0.5):.3f}:d=0.5[a]",
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{b - a:.3f}", "-movflags", "+faststart", str(out),
    ], stdin=render.stdout)
    render.stdout.close()
    ff.wait()
    render.wait()
    if render.returncode != 0 or ff.returncode != 0:
        sys.exit(f"出片失败：叠加层返回 {render.returncode}，ffmpeg 返回 {ff.returncode}。"
                 f"先运行 overlay_engine.py <作品目录> check 找出问题")
    print("成片完成", out)

if STEP in ("sheet", "all"):
    src = WORK / "成片.mp4"
    if not src.exists():
        sys.exit("还没有 成片.mp4")
    from PIL import Image

    cols, tw, th = 4, 480, 270
    times = INFO["preview_times"]
    sheet = Image.new("RGB", (cols * tw, ((len(times) + cols - 1) // cols) * th))
    tmp = WORK / "_frame.jpg"
    for n, t in enumerate(times):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{max(0, t - T0):.3f}", "-i", str(src),
                        "-frames:v", "1", "-vf", f"scale={tw}:{th}", str(tmp)], check=True)
        sheet.paste(Image.open(tmp), ((n % cols) * tw, (n // cols) * th))
    tmp.unlink(missing_ok=True)
    sheet.save(WORK / "成片_总览.jpg", quality=88)
    print(WORK / "成片_总览.jpg")
