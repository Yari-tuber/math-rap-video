"""新建一个作品目录。
用法:
    python new_project.py <作品目录>            # 复制样例"数线段"（歌词、分镜、图形）作为起点
    python new_project.py <作品目录> --blank    # 空白模板：只有骨架和填写说明
目录已存在且非空时不会覆盖。
"""
import shutil
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):  # 系统编码不支持中文时也不要崩
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

args = [a for a in sys.argv[1:] if not a.startswith("-")]
if len(args) != 1 or any(a in ("-h", "--help") for a in sys.argv[1:]):
    print(__doc__)
    sys.exit(0 if any(a in ("-h", "--help") for a in sys.argv[1:]) else 1)
unknown = [a for a in sys.argv[1:] if a.startswith("-") and a != "--blank"]
if unknown:
    sys.exit(f"不认识的参数 {unknown}。用法见 --help")
dst = Path(args[0]).resolve()
blank = "--blank" in sys.argv
src = Path(__file__).resolve().parent.parent / ("templates/blank" if blank else "examples/shuxianduan")
if dst.exists() and any(dst.iterdir()):
    sys.exit(f"{dst} 已存在且不是空的，换一个目录名")
dst.mkdir(parents=True, exist_ok=True)
for f in src.iterdir():
    if f.is_file():
        shutil.copy2(f, dst / f.name)
print(f"已创建 {dst}（来自{'空白模板' if blank else '样例：数线段'}）")
print("接下来：1) 改 lyrics.md（歌词）   2) 拿到音频后运行 prepare_audio.py   3) 改 storyboard.json 和 graphics.py")
