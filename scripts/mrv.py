"""math-rap-video 的唯一入口。每条命令做完都会打印「下一步」那条完整命令，照抄就行；不知道做到哪了就跑 next。

    python mrv.py doctor [--fix] [--python 路径] [--demucs-python 路径] [--model 路径]   检查环境；--fix 自动装
    python mrv.py new    <作品目录> [--style 画风] [--blank]       新建作品（默认复制样例：数线段）
    python mrv.py lyrics <作品目录>                                歌词体检 + 生成送唱版和各平台提示词（给音乐模型/）
    python mrv.py key    <平台> [--file 存密钥的文件]              保存音乐模型的密钥（只存在这台电脑上，不显示）
    python mrv.py music  <作品目录> --api elevenlabs [--takes 2]   有接口：直接生成几版歌
    python mrv.py song   <作品目录> [--song 歌1.mp3 歌2.mp3 …]     丢进几版歌：分人声、逐字对齐、检查、自动挑最好的一版
    python mrv.py pick   <作品目录> <版本名>                       换成另一版（比如 生成_02）
    python mrv.py check  <作品目录>                                分镜和画面检查 + 每句一格的预览图
    python mrv.py render <作品目录> [--part 起 止] [--vertical]    出片
    python mrv.py next   <作品目录>                                告诉你下一步该做什么
    python mrv.py styles                                          有哪些画风

退出码：0 通过；2 缺环境（会给修复命令）；3 这版音频建议换（不是程序错误，不要改代码）；4 检查没过（会说第几句、改什么）。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE))
import mrv_config as cfg  # noqa: E402
from mrv_sing import build as build_sing, is_hook, parse_lyrics  # noqa: E402
from mrv_style import list_styles  # noqa: E402

MRV = HERE / "mrv.py"
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


def cmd(*parts):
    """打印用的完整命令：绝对路径、带引号，照抄就能跑。"""
    py = sys.executable
    return " ".join([f'"{py}"', f'"{MRV}"'] + [f'"{p}"' if (" " in str(p) or os.sep in str(p) or "/" in str(p)) else str(p)
                                               for p in parts])


def nxt(text):
    print(f"\n下一步：{text}")


def run(argv, **kw):
    return subprocess.run([str(a) for a in argv], **kw)


def work_dir(p, must=True):
    w = Path(p).resolve()
    if must and not w.is_dir():
        sys.exit(f"错误：作品目录不存在：{w}。先跑 {cmd('new', w)}")
    return w


def lyrics_file(w):
    return next((w / n for n in ("lyrics.md", "歌词.md") if (w / n).exists()), None)


def bpm_of(w):
    lp = lyrics_file(w)
    meta = parse_lyrics(lp)[0] if lp else {}
    return float(meta.get("bpm") or 90)


# ---------------------------------------------------------------- doctor
def has_mod(py, mod):
    return run([py, "-c", f"import {mod}"], capture_output=True).returncode == 0


def doctor(a):
    if a.python:
        p = Path(a.python)
        if not p.exists():
            sys.exit(f"错误：{p} 不存在")
        cfg.set_(("python"), str(p))
        print(f"已记下：对时间用的 Python = {p}")
    if a.demucs_python:
        cfg.set_("demucs_python", str(Path(a.demucs_python)))
        print(f"已记下：分人声用的 Python = {a.demucs_python}")
    if a.model:
        cfg.set_("aligner_model", a.model)
        print(f"已记下：对齐模型 = {a.model}")
    if a.fix:
        fix_env()
    ok = True

    def line(good, what, how=""):
        nonlocal ok
        ok = ok and good
        print(f"  {'✓' if good else '✗'} {what}" + ("" if good else f"\n      怎么办：{how}"))

    print(f"Python {sys.version.split()[0]}（{sys.executable}）")
    line(sys.version_info >= (3, 10), "Python 3.10 以上", "装 Python 3.12：Windows 用 winget install Python.Python.3.12，或去 python.org")
    line(bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe")), "ffmpeg / ffprobe",
         "Windows：winget install Gyan.FFmpeg；macOS：brew install ffmpeg；Linux：包管理器装 ffmpeg")
    for m, pip in [("PIL", "pillow"), ("numpy", "numpy"), ("librosa", "librosa"), ("pypinyin", "pypinyin")]:
        line(has_mod(sys.executable, m), m, f'"{sys.executable}" -m pip install {pip}')
    hp, dp = cfg.heavy_python(), cfg.demucs_python()
    print(f"逐字对齐用的 Python：{hp}")
    for m in ("torch", "transformers"):
        line(has_mod(hp, m), m, f"跑 {cmd('doctor', '--fix')} 自动装；已经有装好的环境就 {cmd('doctor', '--python', '<那个python.exe>')}")
    if dp != hp:
        print(f"分人声用的 Python：{dp}")
    line(has_mod(dp, "demucs"), "demucs（分人声）",
         f"跑 {cmd('doctor', '--fix')} 自动装；已经有装好 demucs 的环境就 {cmd('doctor', '--demucs-python', '<那个python.exe>')}")
    if has_mod(hp, "transformers"):
        r = run([hp, "-c", "import transformers;print(transformers.__version__)"], capture_output=True, text=True)
        v = r.stdout.strip()
        major_minor = tuple(int(x) for x in re.findall(r"\d+", v)[:2] or [0, 0])
        line(major_minor >= (5, 13), f"transformers 版本 {v}（要 5.13 以上）", f'"{hp}" -m pip install -U "transformers>=5.13"')
    model = cfg.get("aligner_model") or "Qwen/Qwen3-ForcedAligner-0.6B-hf"
    if Path(model).exists():
        line(True, f"对齐模型：{model}")
    else:
        print(f"  · 对齐模型：{model}（第一次对时间时自动下载约 1.8 GB；国内先设环境变量 HF_ENDPOINT=https://hf-mirror.com，"
              f"或者从 ModelScope 下好后 {cmd('doctor', '--model', '<模型文件夹>')}）")
    from mrv_paths import library_dir
    lib = library_dir(None, None)
    print(f"  · 背景素材库：{'有（' + str(lib) + '）' if (lib / 'library.json').exists() else '没装。只用纯色 / 网格 / 黑板背景的画风（chalk、glow）不需要它；要用暗色电影感（cinema）就装：python ' + str(HERE / 'install.py') + ' --library <backgrounds_library.zip>'}")
    keys = [p for p in ("elevenlabs",) if cfg.get_key(p)]
    print(f"  · 音乐模型密钥：{'、'.join(keys) if keys else '没有（没关系：没有接口就用网页生成，见 给音乐模型/）'}")
    print("\n环境齐了。" if ok else "\n有 ✗ 的照「怎么办」处理，处理完再跑一次 doctor。")
    if not ok:
        sys.exit(2)


def fix_env():
    """建一个独立环境（~/.math-rap-video/venv），把对时间要用的都装进去，不碰你系统里的 Python。"""
    venv = cfg.HOME / "venv"
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if sys.version_info < (3, 11):
        sys.exit("错误：对齐要 transformers 5.13，它要 Python 3.11 以上。先装 Python 3.12，用它来跑 mrv.py doctor --fix")
    if not py.exists():
        print(f"建独立环境 {venv} …")
        run([sys.executable, "-m", "venv", venv], check=True)
    mirror = []
    try:
        import urllib.request
        urllib.request.urlopen("https://pypi.org/simple/pip/", timeout=6)
    except Exception:  # noqa: BLE001
        mirror = ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
        print("连不上 PyPI，改用清华镜像")
    pip = [py, "-m", "pip", "install", "-U", *mirror]
    print("装基础包（几十 MB）…")
    run(pip + ["pip", "pillow", "numpy", "librosa", "pypinyin"], check=True)
    print("装 torch（CPU 版约 200 MB；有 NVIDIA 显卡想更快，装完再按 pytorch.org 换 CUDA 版）…")
    run(pip + ["torch"], check=True)
    print("装 transformers 和 demucs …")
    run(pip + ["transformers>=5.13", "demucs>=4.1", "soundfile"], check=True)
    cfg.set_("python", str(py))
    print(f"装好了，已记下：对时间用 {py}")
    print("对齐模型第一次用时自动下载（约 1.8 GB）。国内网络先设 HF_ENDPOINT=https://hf-mirror.com")


# ---------------------------------------------------------------- new / styles
def new(a):
    w = Path(a.work).resolve()
    if w.exists() and any(w.iterdir()):
        sys.exit(f"错误：{w} 已存在且不是空的，换一个目录名")
    src = SKILL / ("templates/blank" if a.blank else f"examples/{a.example}")
    if not src.is_dir():
        have = ", ".join(p.name for p in (SKILL / "examples").iterdir() if p.is_dir())
        sys.exit(f"错误：没有样例「{a.example}」。有：{have}")
    w.mkdir(parents=True, exist_ok=True)
    for f in src.iterdir():
        if f.is_file():
            shutil.copy2(f, w / f.name)
    sb = w / "storyboard.json"
    if sb.exists() and a.style:
        j = json.loads(sb.read_text(encoding="utf-8"))
        j["style"] = a.style
        sb.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已创建 {w}（{'空白模板' if a.blank else '样例：' + a.example}{'，画风 ' + a.style if a.style else ''}）")
    nxt(f"按 {SKILL / 'prompts' / '写词.md'} 写口诀和歌词，覆盖 {w / 'lyrics.md'}，然后跑\n  {cmd('lyrics', w)}")


def styles(_a):
    print("画风（storyboard.json 里写 \"style\": \"名字\"）：")
    for s in list_styles():
        print(f"  {s['id']:8s} {s['name']}{'（你自己的）' if s['mine'] else ''}\n           {s['desc']}")
    print(f"\n自己做一个：复制 {SKILL / 'styles' / 'cinema'} 到 {cfg.HOME / 'styles' / '<新名字>'}，改 style.json 里的颜色、字体、背景")


# ---------------------------------------------------------------- lyrics / key / music
def lyrics(a):
    w = work_dir(a.work)
    if not lyrics_file(w):
        sys.exit(f"错误：{w} 里没有 lyrics.md。把 {SKILL / 'prompts' / '写词.md'} 里的提示词交给 AI 写歌词，存成 lyrics.md")
    r = run([sys.executable, HERE / "check_lyrics.py", w])
    if r.returncode != 0:
        sys.exit(4)
    print()
    for line in build_sing(w):
        print(line)
    keys = [p for p in ("elevenlabs",) if cfg.get_key(p)]
    nxt("先问用户：「你有没有音乐模型的 API？」\n"
        f"  有（现在支持 ElevenLabs）：让用户给密钥，跑 {cmd('key', 'elevenlabs')} 保存，再跑\n"
        f"      {cmd('music', w, '--api', 'elevenlabs', '--takes', '2')}"
        + ("（这台电脑已经存了 ElevenLabs 密钥）" if keys else "") + "\n"
        f"  没有：打开 {w / '给音乐模型'}，按用户用的平台（Suno.md / 海绵音乐.md / Mureka.md / 通用.md）照着生成 2–3 首，下载回来跑\n"
        f"      {cmd('song', w, '--song', '第一首.mp3', '第二首.mp3')}")


def key(a):
    from music_api import get
    prov = get(a.provider)
    if a.file:
        k = Path(a.file).read_text(encoding="utf-8").strip()
    elif sys.stdin.isatty():
        import getpass
        print(f"{prov.TITLE} 的密钥去这里拿：{prov.KEY_HELP}")
        k = getpass.getpass("粘贴密钥（不会显示），回车：").strip()
    else:
        k = sys.stdin.read().strip()
    if len(k) < 10:
        sys.exit("错误：密钥太短，可能没粘全")
    cfg.save_key(prov.NAME, k)
    print(f"已保存 {prov.TITLE} 的密钥到 {cfg.KEYS}（只在这台电脑上，不会进作品目录，也不会打印出来）")


def music(a):
    from music_api import get
    w = work_dir(a.work)
    prov = get(a.api)
    if not (w / "唱词.md").exists() or (lyrics_file(w) and (w / "唱词.md").stat().st_mtime < lyrics_file(w).stat().st_mtime):
        for line in build_sing(w):
            print(line)
    k = cfg.get_key(prov.NAME)
    if not k and not a.dry:
        sys.exit(f"错误：没有 {prov.TITLE} 的密钥。{prov.KEY_HELP}\n"
                 f"  拿到后跑 {cmd('key', prov.NAME)}；没有接口也没关系：打开 {w / '给音乐模型'} 用网页生成。")
    _, secs = parse_lyrics(w / "唱词.md")
    sections = [{"name": s["name"], "lines": [t for _, t in s["lines"]]} for s in secs]
    print(f"{prov.TITLE}：{prov.COST_HELP}。这会花用户的额度。")
    made = prov.generate(w, sections, bpm=bpm_of(w), takes=a.takes, key=k, preset=a.preset, dry=a.dry,
                         intro_bars=int(cfg.get("intro_bars", 2)))
    if made:
        nxt(f"{cmd('song', w)}（会自动用 歌/ 里的这几版，量哪一版最好）")


# ---------------------------------------------------------------- song
def read_embedded_lyrics(song):
    r = run(["ffprobe", "-v", "error", "-show_entries", "stream_tags:format_tags", "-of", "json", song],
            capture_output=True, text=True, encoding="utf-8")
    try:
        info = json.loads(r.stdout or "{}")
    except json.JSONDecodeError:
        return ""
    tags = {}
    for st in info.get("streams", []) + [info.get("format", {})]:
        tags.update(st.get("tags", {}) or {})
    return next((v for k, v in tags.items() if k.lower().startswith(("lyrics", "unsyncedlyrics"))), "")


def lyrics_from_text(raw, title):
    out, n, cur = [f"# {title}", "", "- 歌词草稿：从音频里嵌的歌词读出来的。必须和实际唱的一字不差：漏唱的删掉、重复唱的写两遍", ""], 0, None
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^[\[【(（](.+?)[\]】)）]$", s)
        if m:
            cur = m.group(1).split(" - ")[0].strip()
            out.append(f"## [{cur}]")
            continue
        s = re.sub(r"[“”\"「」『』]", "", s)
        s = re.sub(r"\s+", "，", s).strip("，")
        if not s:
            continue
        if cur is None:
            cur = "Verse 1"
            out.append("## [Verse 1]")
        n += 1
        out.append(f"{n}. {s}")
    return "\n".join(out) + "\n", n


def vocal_energy(vocals, lines):
    """每句人声的响度（dB），用来查「这句可能没唱」。"""
    import numpy as np
    raw = run(["ffmpeg", "-v", "error", "-i", vocals, "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
              capture_output=True).stdout
    x = np.frombuffer(raw, "<f4")
    out = []
    for ln in lines:
        seg = x[int(ln["start"] * 16000):max(int(ln["start"] * 16000) + 1, int(ln["end"] * 16000))]
        rms = float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0
        out.append(20 * np.log10(rms + 1e-9))
    return out


def song(a):
    w = work_dir(a.work)
    (w / "歌").mkdir(exist_ok=True)
    takes = []
    for f in a.song or []:
        p = Path(f).resolve()
        if not p.exists():
            sys.exit(f"错误：找不到 {p}")
        try:
            p.relative_to(w)
            takes.append(p)
        except ValueError:
            dst = w / "歌" / p.name
            shutil.copy2(p, dst)
            takes.append(dst)
    if not takes:
        takes = sorted(p for p in (w / "歌").iterdir() if p.suffix.lower() in AUDIO_EXT and not p.name.startswith("_"))
    if not takes:
        sys.exit(f"错误：没有音频。用 --song 指定，或者放进 {w / '歌'}")
    # 歌词：没有 lyrics.md 就读 Suno 嵌在 mp3 里的
    if not lyrics_file(w):
        raw = read_embedded_lyrics(takes[0])
        if not raw:
            sys.exit(f"错误：{w} 里没有 lyrics.md，{takes[0].name} 里也没有嵌歌词。把唱的歌词存成 lyrics.md（一句一行 '1. 歌词'）")
        text, n = lyrics_from_text(raw, w.name)
        (w / "lyrics.md").write_text(text, encoding="utf-8")
        print(f"从 {takes[0].name} 读到嵌着的歌词 {n} 句，写成 lyrics.md 草稿。音乐模型常常跳过、重复某几句，对完下面的检查要核对")
    lp = lyrics_file(w)
    if not (w / "唱词.md").exists() or (w / "唱词.md").stat().st_mtime < lp.stat().st_mtime or \
            ((w / "读音替换.json").exists() and (w / "唱词.md").stat().st_mtime < (w / "读音替换.json").stat().st_mtime):
        for line in build_sing(w):
            print(line)
    _, sung_secs = parse_lyrics(w / "唱词.md")
    _, show_secs = parse_lyrics(lp)
    sung = {n: t for s in sung_secs for n, t in s["lines"]}
    show = {n: t for s in show_secs for n, t in s["lines"]}
    hook_lines = [n for s in show_secs if is_hook(s["name"]) for n, _ in s["lines"]]
    koujue = re.sub(r"[\W_]", "", parse_lyrics(lp)[0].get("口诀", ""))   # 头信息里写的口诀：凡是唱到它的句子都算「要听清」
    if len(koujue) >= 4:
        hook_lines = sorted(set(hook_lines) | {n for n, t in show.items() if koujue[:4] in re.sub(r"[\W_]", "", t)})
    (w / "_对齐").mkdir(exist_ok=True)
    txt = w / "_对齐" / "唱词.txt"
    txt.write_text("\n".join(sung[n] for n in sorted(sung)) + "\n", encoding="utf-8")
    hp, dp = cfg.heavy_python(), cfg.demucs_python()
    need = [(hp, m) for m in ("torch", "transformers")] + ([] if a.no_separate else [(dp, "demucs")])
    for py, m in need:
        if not has_mod(py, m):
            print(f"错误：{py} 没装 {m}。\n  跑 {cmd('doctor', '--fix')} 自动装；"
                  f"或者用 doctor 的 --python / --demucs-python 指向已经装好的环境")
            sys.exit(2)
    bpm = bpm_of(w)
    intro = int(cfg.get("intro_bars", 2))
    results = []
    for take in takes:
        name = take.stem
        print(f"\n━━ {take.name} ━━")
        t0 = time.time()
        voc = w / "_分离" / "htdemucs" / name / "vocals.wav"
        if a.no_separate:
            voc_in = take
        elif voc.exists():
            voc_in = voc
            print("① 人声：用上次分好的")
        else:
            print("① 分离人声（demucs；第一次要下约 80 MB 模型，一首歌 1–3 分钟）…", flush=True)
            r = run([dp, "-m", "demucs", "--two-stems", "vocals", "-o", w / "_分离", take],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0 or not voc.exists():
                sys.exit(f"错误：分离人声失败。\n{(r.stderr or '')[-800:]}\n"
                         f"  先跑 {cmd('doctor')} 看缺什么；实在分不了加 --no-separate 用原曲对齐（会差一些）")
            voc_in = voc
        words = w / "_对齐" / f"{name}.words.json"
        if not words.exists() or words.stat().st_mtime < txt.stat().st_mtime:
            print("② 逐字对齐（第一次要加载约 1.8 GB 模型）…", flush=True)
            r = run([hp, HERE / "align_lyrics.py", "--audio", voc_in, "--text", txt, "--out", words],
                    capture_output=True, text=True, encoding="utf-8", errors="replace")
            print("   " + "\n   ".join(x for x in (r.stdout or "").strip().splitlines()[-2:]))
            if r.returncode != 0 or not words.exists():
                sys.exit(f"错误：逐字对齐失败。\n{(r.stderr or '')[-1200:]}\n  先跑 {cmd('doctor')} 看缺什么")
        else:
            print("② 逐字对齐：用上次的结果")
        print("③ 算节拍和每句每字的时间 …", flush=True)
        out_name = f"timing_{name}.json"
        r = run([sys.executable, HERE / "prepare_audio.py", w, "--audio", take, "--lyrics", "唱词.md", "--words", words,
                 "--bpm", f"{bpm:g}", "--intro-bars", str(intro), "--out", out_name],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not (w / out_name).exists():
            sys.exit(f"错误：算时间失败。\n{(r.stderr or r.stdout or '')[-1200:]}")
        T = json.loads((w / out_name).read_text(encoding="utf-8"))
        for ln in T["lines"]:
            ln["show"] = show.get(ln["i"], ln["text"])
        en = vocal_energy(voc_in, T["lines"])
        med = sorted(en)[len(en) // 2]
        silent = [ln["i"] for ln, e in zip(T["lines"], en) if e < med - 16]
        crowded = [ln["i"] for ln in T["lines"] if (ln["end"] - ln["start"]) / max(1, len(ln["text"])) < 0.07]
        rep = T["report"]
        problems = list(rep.get("problems", []))
        if silent:
            problems.append(f"第 {silent} 句几乎没有人声，很可能没唱")
        if crowded and not rep.get("skipped_lines"):
            problems.append(f"第 {crowded} 句的字被挤成一团，可能漏唱或唱得太快")
        on_bar = int(str(rep.get("lines_on_downbeat", "0/1")).split("/")[0])
        hook_bad = [n for n in hook_lines if n in silent or n in crowded or n in rep.get("skipped_lines", [])]
        rep.update(silent_lines=silent, crowded_lines=crowded, hook_bad=hook_bad, problems=problems,
                   verdict="换一版" if problems else "可用", energy_db=[round(e, 1) for e in en])
        (w / out_name).write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
        results.append({"name": name, "file": take, "T": T, "on_bar": on_bar, "problems": problems,
                        "hook_bad": hook_bad, "entry": rep.get("entry_bars"), "secs": time.time() - t0})
        print(f"   速度 {T['bpm']} BPM，人声在第 {rep.get('entry_bars')} 小节进，落在小节头 {rep.get('lines_on_downbeat')}，"
              f"用了 {time.time() - t0:.0f} 秒")
        print("   结论：" + ("可用" if not problems else "建议换一版。" + "；".join(problems)))
    # 挑一版：可用 > 口诀那几句没问题 > 问题句少 > 落在小节头的多 > 人声进得准
    best = sorted(results, key=lambda r: (bool(r["problems"]), len(r["hook_bad"]), len(r["problems"]),
                                          -r["on_bar"], abs((r["entry"] or 0) - intro)))[0]
    shutil.copy2(w / f"timing_{best['name']}.json", w / "timing.json")
    listen = sorted(set(best["T"]["report"].get("low_match_lines", [])) | set(hook_lines))
    state = {"timing_from": best["name"], "audio": best["T"]["audio"], "listen_lines": listen,
             "takes": {r["name"]: ("可用" if not r["problems"] else "换一版") for r in results}}
    (w / "状态.json").write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n━━ 选了 {best['name']} ━━（{len(results)} 版里："
          + "，".join(f"{r['name']} {'可用' if not r['problems'] else '换一版'}" for r in results) + "）")
    print(f"已写成 timing.json。交付时请用户重点听第 {listen} 句（口诀那几句一定要听清）。")
    if best["problems"]:
        print("\n结论：每一版都建议换（这不是程序错误，不要改代码、也不要改歌词去迁就）。两个选择：\n"
              f"  ① 再生成一两版音频，放进 {w / '歌'}，重跑 {cmd('song', w)}\n"
              f"  ② 接受现在这版，交付时告诉用户上面那几句要听\n  想换成别的版本：{cmd('pick', w, '<版本名>')}")
        sys.exit(3)
    if not (w / "storyboard.json").exists():
        nxt(f"写 storyboard.json 和 graphics.py（照 {SKILL / 'examples'} 里的样例，写法见 {SKILL / 'references' / 'visuals.md'}），然后\n  {cmd('check', w)}")
    else:
        nxt(cmd("check", w))


def pick(a):
    w = work_dir(a.work)
    src = w / f"timing_{a.name}.json"
    if not src.exists():
        have = ", ".join(p.stem[7:] for p in w.glob("timing_*.json"))
        sys.exit(f"错误：没有 {src.name}。有：{have}")
    shutil.copy2(src, w / "timing.json")
    st = json.loads((w / "状态.json").read_text(encoding="utf-8")) if (w / "状态.json").exists() else {}
    st["timing_from"] = a.name
    (w / "状态.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"换成了 {a.name}。分镜和图形不用改（时间都是按歌词写的）")
    nxt(cmd("check", w))


# ---------------------------------------------------------------- check / render / next
def check(a):
    w = work_dir(a.work)
    eng = HERE / "overlay_engine.py"
    r = run([sys.executable, eng, w, "check"])
    if r.returncode != 0:
        print("\n检查没过：按上面的提示改 storyboard.json / graphics.py，再跑一次。")
        sys.exit(4)
    # 先把背景铺好，预览图里垫的就是真实的背景镜头，看得出镜头和图形搭不搭
    bgv = w / "成片_背景.mp4"
    newest = max((w / f).stat().st_mtime for f in ("storyboard.json", "timing.json") if (w / f).exists())
    if not bgv.exists() or bgv.stat().st_mtime < newest:
        print("\n铺背景（预览图要垫真实的背景镜头，约 1 分钟）…", flush=True)
        r = run([sys.executable, HERE / "build_video.py", w, "bg"], capture_output=True, text=True, encoding="utf-8",
                errors="replace")
        if r.returncode != 0:
            last = ((r.stderr or r.stdout or "").strip().splitlines() or [""])[-1]
            print(f"  背景没铺成，预览图先用暗色底。{last}")
    run([sys.executable, eng, w, "sheet", "--pages"])
    print(f"\n预览图：{w / '分镜预览.jpg'}（每句一格，垫的是真实背景）和 分镜预览_p1.jpg…（大图）。"
          "能看图就打开看：每句画面对不对、字有没有压住、背景镜头和图形搭不搭。")
    nxt(f"{cmd('render', w, '--part', '<起秒>', '<止秒>')} 先出 10 秒看看；没问题再 {cmd('render', w)}")


def render(a):
    w = work_dir(a.work)
    bv = HERE / "build_video.py"
    if a.part:
        if not (w / "成片_背景.mp4").exists():
            run([sys.executable, bv, w, "bg"], check=True)
        r = run([sys.executable, bv, w, "final", str(a.part[0]), str(a.part[1])])
        if r.returncode == 0:
            print(f"片段：{w / '成片_片段.mp4'}")
            nxt(f"看过没问题就出全片：{cmd('render', w)}（全片 6–12 分钟，放后台跑）")
        sys.exit(r.returncode)
    r = run([sys.executable, bv, w, "all"])
    if r.returncode != 0:
        sys.exit(r.returncode)
    if a.vertical:
        run([sys.executable, HERE / "make_vertical.py", w], check=True)
    st = json.loads((w / "状态.json").read_text(encoding="utf-8")) if (w / "状态.json").exists() else {}
    print(f"\n成片：{w / '成片.mp4'}" + (f"，竖屏：{w / '成片_竖屏.mp4'}" if a.vertical else ""))
    if st.get("listen_lines"):
        print(f"交付时告诉用户：画面和时间都检查过，声音要人听一遍，尤其第 {st['listen_lines']} 句。")


def next_step(a):
    w = Path(a.work).resolve()
    if not w.is_dir():
        nxt(cmd("new", w))
        return
    lp = lyrics_file(w)
    songs = [p for p in (w / "歌").iterdir() if p.suffix.lower() in AUDIO_EXT] if (w / "歌").is_dir() else []
    if not lp and not songs:
        nxt(f"按 {SKILL / 'prompts' / '写词.md'} 写歌词，存成 {w / 'lyrics.md'}，然后 {cmd('lyrics', w)}")
    elif lp and not (w / "唱词.md").exists():
        nxt(cmd("lyrics", w))
    elif not songs and not (w / "timing.json").exists():
        nxt(f"问用户有没有音乐模型的 API：有就 {cmd('music', w, '--api', 'elevenlabs')}；"
            f"没有就打开 {w / '给音乐模型'} 用网页生成，下载回来 {cmd('song', w, '--song', '歌.mp3')}")
    elif not (w / "timing.json").exists():
        nxt(cmd("song", w))
    elif not (w / "storyboard.json").exists() or not (w / "graphics.py").exists():
        nxt(f"写 storyboard.json 和 graphics.py（照 {SKILL / 'examples'}），然后 {cmd('check', w)}")
    elif not (w / "分镜预览.jpg").exists() or (w / "分镜预览.jpg").stat().st_mtime < max(
            (w / f).stat().st_mtime for f in ("storyboard.json", "graphics.py", "timing.json")):
        nxt(cmd("check", w))
    elif not (w / "成片.mp4").exists():
        nxt(cmd("render", w))
    else:
        print(f"已经出片了：{w / '成片.mp4'}。改了东西就重跑 {cmd('check', w)} 和 {cmd('render', w)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("doctor"); p.add_argument("--fix", action="store_true"); p.add_argument("--python")
    p.add_argument("--demucs-python"); p.add_argument("--model")
    p.set_defaults(fn=doctor)
    p = sp.add_parser("new"); p.add_argument("work"); p.add_argument("--style"); p.add_argument("--blank", action="store_true")
    p.add_argument("--example", default="shuxianduan"); p.set_defaults(fn=new)
    p = sp.add_parser("styles"); p.set_defaults(fn=styles)
    p = sp.add_parser("lyrics"); p.add_argument("work"); p.set_defaults(fn=lyrics)
    p = sp.add_parser("key"); p.add_argument("provider"); p.add_argument("--file"); p.set_defaults(fn=key)
    p = sp.add_parser("music"); p.add_argument("work"); p.add_argument("--api", required=True)
    p.add_argument("--takes", type=int, default=2); p.add_argument("--preset", default="chant")
    p.add_argument("--dry", action="store_true"); p.set_defaults(fn=music)
    p = sp.add_parser("song"); p.add_argument("work"); p.add_argument("--song", nargs="*")
    p.add_argument("--no-separate", action="store_true"); p.set_defaults(fn=song)
    p = sp.add_parser("pick"); p.add_argument("work"); p.add_argument("name"); p.set_defaults(fn=pick)
    p = sp.add_parser("check"); p.add_argument("work"); p.set_defaults(fn=check)
    p = sp.add_parser("render"); p.add_argument("work"); p.add_argument("--part", nargs=2, type=float)
    p.add_argument("--vertical", action="store_true"); p.set_defaults(fn=render)
    p = sp.add_parser("next"); p.add_argument("work"); p.set_defaults(fn=next_step)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
