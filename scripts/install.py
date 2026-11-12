"""把本 skill 装到这台电脑上的各个 AI 工具里，并安放背景素材库。

用法:
    python install.py --list                      # 看这台电脑上找到了哪些 AI 工具
    python install.py --to all                    # 装到常用位置 + 这台电脑上找到的工具，顺便下好背景素材库（推荐）
    python install.py --to all --no-library       # 只装 skill，不下素材库（只用黑板 / 发光画风时可以不要）
    python install.py --get-library               # 只下背景素材库（97 MB，26 段 AI 生成的暗色镜头）
    python install.py --to dsh claude             # 只装到指定的工具
    python install.py --to D:/somewhere/skills    # 装到任意文件夹（会在里面建 math-rap-video/）
    python install.py --library 素材库_背景.zip    # 安放背景素材库（zip 或已解压的文件夹）
    python install.py --to all --library 素材库_背景.zip   # 两件事一起做

说明:
- 各工具存放 skill 的文件夹：
    agents    ~/.agents/skills   通用位置：Codex、Gemini CLI、opencode、Cursor、DeepSeek Harness、Kimi 都读（总是装）
    claude    ~/.claude/skills   Claude Code、Claude 桌面版（总是装）
    dsh       ~/.dsh/skills      DeepSeek Harness（总是装）
    其他（这台电脑上有才装）：trae、trae-cn、qoder、codebuddy、lingma、qwen、opencode、gemini
    codex-legacy ~/.codex/skills  旧版 Codex，只有点名时才装
- 装完要在那个 AI 工具里新开一个对话，它才认得出来。
- 素材库放到共享位置 ~/.math-rap-video/backgrounds/，各工具里的副本都会自动找到它，
  所以 skill 副本本身不带视频文件，只有几百 KB。
- 重复运行是安全的：已有的同名 skill 会被新版本替换；素材库已存在时不会重复复制。
- 卸载：删掉对应工具 skills 文件夹里的 math-rap-video 文件夹即可。
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

SKILL = Path(__file__).resolve().parent.parent
NAME = "math-rap-video"
HOME = Path.home()
SHARED = HOME / ".math-rap-video" / "backgrounds"
TOOLS = {
    "agents": HOME / ".agents" / "skills",
    "claude": HOME / ".claude" / "skills",
    "dsh": HOME / ".dsh" / "skills",
    "trae": HOME / ".trae" / "skills",
    "trae-cn": HOME / ".trae-cn" / "skills",
    "qoder": HOME / ".qoder" / "skills",
    "codebuddy": HOME / ".codebuddy" / "skills",
    "lingma": HOME / ".lingma" / "skills",
    "qwen": HOME / ".qwen" / "skills",
    "opencode": HOME / ".config" / "opencode" / "skills",
    "gemini": HOME / ".gemini" / "skills",
    "codex-legacy": HOME / ".codex" / "skills",
}
ALWAYS = ("agents", "claude", "dsh")          # 这三处不管有没有都建
LIBRARY_URL = "https://github.com/Yari-tuber/math-rap-video/releases/download/v1.0.0/backgrounds_library.zip"

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--list", action="store_true", help="列出找到的 AI 工具")
ap.add_argument("--to", nargs="+", metavar="工具或文件夹", help="all、工具名，或任意文件夹路径")
ap.add_argument("--library", metavar="zip或文件夹", help="背景素材库的压缩包或文件夹")
ap.add_argument("--get-library", action="store_true", help="从 GitHub 下载背景素材库（97 MB）")
ap.add_argument("--no-library", action="store_true", help="装 skill 时不顺便下载素材库")
args = ap.parse_args()
if not (args.list or args.to or args.library or args.get_library):
    print(__doc__)
    sys.exit(0)


def count_clips(d):
    return len(list(Path(d).glob("*.mp4")))


def find_library_root(d):
    """library.json 可能在压缩包根目录，也可能在里面的一层文件夹里。"""
    d = Path(d)
    if (d / "library.json").exists():
        return d
    hits = sorted(d.glob("*/library.json")) + sorted(d.glob("*/*/library.json"))
    return hits[0].parent if hits else None


def place_library(src):
    src = Path(src).expanduser()
    if not src.exists():
        sys.exit(f"找不到 {src}")
    SHARED.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        if not zipfile.is_zipfile(src):
            sys.exit(f"{src} 不是 zip 压缩包")
        tmp = SHARED.parent / "_unzip_tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        root = find_library_root(tmp)
    else:
        tmp, root = None, find_library_root(src)
    if root is None:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(f"{src} 里没有 library.json，不像是素材库")
    n = 0
    for f in root.iterdir():
        if f.is_file() and f.suffix.lower() in (".mp4", ".json", ".jpg", ".png", ".md", ".txt"):
            dst = SHARED / f.name
            if not dst.exists() or dst.stat().st_size != f.stat().st_size or f.suffix.lower() == ".json":
                shutil.copy2(f, dst)
                n += 1
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[OK] 素材库已放到 {SHARED}（{count_clips(SHARED)} 段背景，本次复制 {n} 个文件）")


def ensure_shared_library():
    """要装到别的工具时，如果共享位置还没有素材库而本 skill 自带，就先放一份过去。"""
    if (SHARED / "library.json").exists():
        return
    bundled = SKILL / "assets" / "backgrounds"
    if (bundled / "library.json").exists():
        place_library(bundled)


def install_to(dest_parent, label):
    dest = Path(dest_parent).expanduser() / NAME
    if dest.resolve() == SKILL.resolve():
        print(f"[跳过] {label}：正在运行的就是这一份（{dest}）")
        return
    if dest.exists():
        shutil.rmtree(dest)

    def ignore(folder, names):
        skip = {"__pycache__", ".git", ".github", ".gitignore", "docs", "tests"}
        if Path(folder).resolve() == (SKILL / "assets" / "backgrounds").resolve():
            skip |= {n for n in names if n.lower().endswith(".mp4")}   # 视频只留在共享位置
        return skip & set(names)

    shutil.copytree(SKILL, dest, ignore=ignore)
    print(f"[OK] {label}：已安装到 {dest}")


if args.list:
    print("这台电脑上的 AI 工具 skill 文件夹：")
    for k, p in TOOLS.items():
        state = "没有找到这个工具的文件夹"
        if p.exists():
            state = "已安装本 skill" if (p / NAME / "SKILL.md").exists() else "找到，还没装本 skill"
        print(f"  {k:9s} {p}  —— {state}")
    lib_ok = (SHARED / "library.json").exists()
    print(f"共享素材库 {SHARED}：" + (f"{count_clips(SHARED)} 段背景" if lib_ok else "还没有"))

if (args.get_library or (args.to and not args.no_library and not args.library)) and not (SHARED / "library.json").exists():
    import tempfile
    import urllib.request
    tmp = Path(tempfile.gettempdir()) / "mrv_backgrounds_library.zip"
    print(f"下载背景素材库（97 MB）：{LIBRARY_URL}")
    try:
        with urllib.request.urlopen(LIBRARY_URL, timeout=60) as r, open(tmp, "wb") as f:
            total, got = int(r.headers.get("Content-Length") or 0), 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                got += len(b)
                if total:
                    print(f"\r  {got * 100 // total}%", end="", flush=True)
        print()
        place_library(tmp)
    except Exception as e:  # noqa: BLE001
        print(f"下载失败（{e}）。可以用浏览器打开上面的地址下载，再运行：python install.py --library <下载的zip>")
    finally:
        tmp.unlink(missing_ok=True)
elif args.get_library or args.to:
    print(f"背景素材库已经在 {SHARED}（{count_clips(SHARED)} 段），不用再下")

if args.library:
    place_library(args.library)

if args.to:
    ensure_shared_library()
    targets = []
    for t in args.to:
        if t == "all":
            targets += [(k, p) for k, p in TOOLS.items() if k in ALWAYS or (p.exists() and k != "codex-legacy")]
        elif t in TOOLS:
            if t in ALWAYS or t == "codex-legacy" or TOOLS[t].exists():
                targets.append((t, TOOLS[t]))
            else:
                print(f"[跳过] {t}：没有找到 {TOOLS[t]}（这个工具可能没装）")
        else:
            Path(t).expanduser().mkdir(parents=True, exist_ok=True)
            targets.append((t, Path(t)))
    for label, p in targets:
        p.mkdir(parents=True, exist_ok=True)
        install_to(p, label)
    if not (SHARED / "library.json").exists():
        print("\n注意：还没有背景素材库（只有暗色电影感画风要用）。要用就运行：python install.py --get-library")
    print("\n装好后新开一个对话，跑一次环境检查：python " + str(Path(__file__).resolve().parent / "mrv.py") + " doctor")
    print("然后在对应的 AI 工具里说：用 math-rap-video 把【知识点】做成口诀说唱讲题视频")
    print("如果那个工具没有自动认出这个 skill，就说：请先阅读 <上面的安装路径>/SKILL.md，然后按里面的流程做")
