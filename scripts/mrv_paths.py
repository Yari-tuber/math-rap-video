"""背景素材库放在哪：几个脚本共用的查找顺序。

1. 调用方明确给的目录（命令行 --lib，或 storyboard.json 的 backgrounds.library）
2. 环境变量 MATH_RAP_LIBRARY
3. 本 skill 的 assets/backgrounds/（里面有 library.json 时）
4. 共享位置 ~/.math-rap-video/backgrounds/（install.py 会把素材库放在这里，
   这样同一台电脑上给几个 AI 工具各装一份 skill，素材库只占一份空间）
5. 都没有时返回第 3 个位置，由调用方报"找不到素材库"
"""
import os
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
BUNDLED = SKILL / "assets" / "backgrounds"
SHARED = Path.home() / ".math-rap-video" / "backgrounds"


def library_dir(explicit=None, base=None):
    """返回素材库目录。explicit 是相对路径时按 base（作品目录）解析。"""
    if explicit:
        p = Path(explicit)
        if not p.is_absolute() and base is not None:
            p = Path(base) / p
        return p
    env = os.environ.get("MATH_RAP_LIBRARY")
    if env:
        return Path(env)
    for cand in (BUNDLED, SHARED):
        if (cand / "library.json").exists():
            return cand
    return BUNDLED


NOT_FOUND_HINT = (
    "找不到背景素材库。任选一种办法：\n"
    f"  1) 运行 python {SKILL / 'scripts' / 'install.py'} --library <素材库压缩包.zip>\n"
    f"  2) 手动把素材库压缩包解压到 {BUNDLED}\n"
    "  3) 设置环境变量 MATH_RAP_LIBRARY 指向素材库文件夹"
)
