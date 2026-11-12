"""给"只能聊天、不能运行命令"的 AI（网页版 ChatGPT、豆包、DeepSeek、Kimi、通义等）准备提示包。

它把要求、规则和样例拼成一个文件。你把这个文件整个粘贴或上传给聊天 AI，它就能写出需要的内容；
脚本仍然由你在自己电脑上运行。

用法:
    python chat_pack.py lyrics "知识点" [--audience "小学四年级"] [--out 文件.md]
        → 给聊天AI_1_写歌词.md：让它写口诀、歌词、分镜表
    python chat_pack.py visuals <作品目录>
        → <作品目录>/给聊天AI_2_写画面.md：让它写 storyboard.json 和 graphics.py
    python chat_pack.py fix <作品目录>
        → <作品目录>/给聊天AI_3_修改.md：自动运行检查，把报错、当前文件一起打包，让它改

完整的一轮：
    1. lyrics → 把 AI 的回答存成 <作品目录>/lyrics.md → python check_lyrics.py <作品目录>
    2. 按 <作品目录>/给音乐模型/ 生成歌 → python mrv.py song <作品目录> --song 歌.mp3
    3. visuals → 把 AI 给的两个文件存进作品目录
    4. fix → 有报错或画面不对就把提示包和预览图一起发给 AI，改完再运行 fix，直到没有问题
    5. python mrv.py render <作品目录>
"""
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

SKILL = Path(__file__).resolve().parent.parent
REF = SKILL / "references"
EX = SKILL / "examples" / "shuxianduan"


def read(p):
    return Path(p).read_text(encoding="utf-8").strip()


def block(title, body, lang=""):
    fence = "````"
    return f"\n\n---\n\n## {title}\n\n{fence}{lang}\n{body}\n{fence}"


def find_lyrics(work):
    for n in ("lyrics.md", "歌词.md"):
        if (work / n).exists():
            return work / n
    sys.exit(f"{work} 里没有 lyrics.md")


argv = sys.argv[1:]
if not argv or argv[0] in ("-h", "--help") or argv[0] not in ("lyrics", "visuals", "fix") or len(argv) < 2:
    print(__doc__)
    sys.exit(0 if argv and argv[0] in ("-h", "--help") else 1)
mode, target = argv[0], argv[1]


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


if mode == "lyrics":
    audience = opt("--audience", "中小学生")
    out = Path(opt("--out", "给聊天AI_1_写歌词.md")).resolve()
    text = f"""# 请帮我写一条"口诀讲解视频"的口诀、歌词和分镜表

知识点：**{target}**
观众：{audience}

我要把这个知识点做成约 1 分钟的说唱讲解视频：一句歌词唱一小节，画面跟着唱词一步步演示。
下面依次是【写作规则】和【一份完整样例】。请严格按规则写，格式和样例保持一致。

## 你要交给我的东西

只输出一个完整的 `lyrics.md` 文件内容（放在一个代码块里），包含：

1. 标题、口诀（8–10 个字）、知识点一句话说明、验算（把例题里每个数字都算一遍写出来）
2. `## [Verse 1]` 14 句、`## [Hook]` 2 句、`## [Verse 2]` 8 句，句子前面带编号 1–24
3. `## 分镜表`：一个表格，三列是「句」「画面」「触发」。"画面"写这一句屏幕上出现什么、怎么动；
   "触发"写唱到这句的哪个字时出现（例如：唱到"四"字）

## 写之前先自查

- 每句 11–15 个字（Verse 2 每句 9–11 个字），全篇押同一个韵
- 口诀在第 6 句完整出现一次，Hook 第 15 句单独再念一次，第 23 句再出现一次
- 例题的数字必须算对；数字的写法避免听错（例如"是四"容易听成"十四"）
- 画面要能"演示道理"，不能只是把歌词打在屏幕上"""
    text += block("写作规则（references/lyrics.md）", read(REF / "lyrics.md"), "markdown")
    text += block("完整样例（数线段）", read(EX / "lyrics.md"), "markdown")
    out.write_text(text + "\n", encoding="utf-8")
    print(f"已生成 {out}（{len(text)} 字）")
    print("下一步：把这个文件整个发给聊天 AI；把它回答里的 lyrics.md 内容存到作品目录，然后运行 check_lyrics.py")
    sys.exit(0)

work = Path(target).resolve()
if not work.is_dir():
    sys.exit(f"找不到作品目录 {work}")
lyrics = read(find_lyrics(work))

RULES = """## 必须遵守的规则

1. **时间一律写成相对歌词的表达式，不写死秒数**：`L(i)` 第 i 句起点，`E(i)` 终点，
   `W(i,'字')` 第 i 句里这个字唱出来的时间（`W(i,'字',2)` 是第 2 个同样的字），`B` 一拍。
   `W()` 里的字必须真的出现在那一句歌词里。
2. **只用下面文档里写明的字段、方法和工具**。不要自己发明 `ctx` 或 `st` 上没有的方法，
   不要直接调用 PIL 的 ImageDraw，不要 import 文档没提到的第三方库。
3. 坐标按 1920×1080 写。主图形放在 y≈180–760；顶部 y<150 是口诀横幅，y≈830 是公式，y≈1010 是字幕，不要画到这些区域里。
4. `graphics.py` 必须有 `draw(canvas, t, ctx)`，结尾用 `st.commit(canvas, alpha)` 贴上去；`setup(ctx)` 里把每个动作的时间算好。
5. 每一句歌词唱的时候，屏幕中间都要有东西（图形、大字或算式），不要出现空画面。
6. 例题里的每个数字、每条线、每个方块的数量都要和歌词一致。
7. 两个文件都要**完整输出**，不要用"其余同上""此处省略"。"""

if mode == "visuals":
    out = work / "给聊天AI_2_写画面.md"
    text = f"""# 请帮我写一条"口诀讲解视频"的画面文件

我有一套现成的渲染程序。它读两个文件，把画面逐帧画出来，再和歌、背景合成视频：

- `storyboard.json`：顶部口诀横幅、公式、弹出的大字、箭头、背景切换计划
- `graphics.py`：这道题专用的图形动画（Python）

下面依次是【规则】【本题的歌词和分镜表】【画面文档】【一份完整样例的两个文件】。
请照着样例的结构，为本题写出这两个文件。

## 你要交给我的东西

两个代码块：第一个是完整的 `storyboard.json`，第二个是完整的 `graphics.py`。除此之外只需要简单说明每一段画了什么。

{RULES}"""
    text += block("本题的歌词和分镜表（lyrics.md）", lyrics, "markdown")
    text += block("画面文档（references/visuals.md）", read(REF / "visuals.md"), "markdown")
    text += block("样例：storyboard.json（数线段）", read(EX / "storyboard.json"), "json")
    text += block("样例：graphics.py（数线段）", read(EX / "graphics.py"), "python")
    out.write_text(text + "\n", encoding="utf-8")
    print(f"已生成 {out}（{len(text)} 字）")
    print("下一步：把这个文件整个发给聊天 AI；把它给的两个文件存进作品目录（覆盖原来的），然后运行：")
    print(f"  python {SKILL / 'scripts' / 'chat_pack.py'} fix \"{work}\"")
    sys.exit(0)

# ---- fix：运行检查，把结果和当前文件打包 ----
for need in ("storyboard.json", "graphics.py"):
    if not (work / need).exists():
        sys.exit(f"{work} 里没有 {need}")
if not (work / "timing.json").exists():
    sys.exit(f"{work} 里还没有 timing.json。先运行 python mrv.py song <作品目录> --song 歌.mp3（需要音频）")
engine = str(SKILL / "scripts" / "overlay_engine.py")
r = subprocess.run([sys.executable, engine, str(work), "check"], capture_output=True, text=True, encoding="utf-8", errors="replace")
report = (r.stdout + ("\n" + r.stderr if r.stderr.strip() else "")).strip()
sheet_ok = False
if r.returncode == 0:
    s = subprocess.run([sys.executable, engine, str(work), "sheet", "--pages"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    sheet_ok = s.returncode == 0
out = work / "给聊天AI_3_修改.md"
status = "检查通过（没有报错）" if r.returncode == 0 else "检查没有通过"
text = f"""# 请帮我修改"口诀讲解视频"的画面文件

我把你上次写的 `storyboard.json` 和 `graphics.py` 放进渲染程序运行了一遍。结果：**{status}**。

- 下面【检查结果】里的每一条报错和"版面提醒"都请处理
- 我同时上传了预览图（每句歌词一格）。请逐格对照分镜表看：该出现的东西有没有出现、
  有没有空的格子、文字和图形有没有互相压住或者超出画面、数量对不对
- 【我的修改意见】如果有内容，以它为准

## 我的修改意见

（在这里写，例如：第 9 句的弧线太低，压到算式了。没有就留空。）

## 你要交给我的东西

改好后的**完整** `storyboard.json` 和**完整** `graphics.py`，各一个代码块。只改有问题的地方，其他保持不变。

{RULES}"""
text += block("检查结果", report or "（没有输出）")
text += block("本题的歌词和分镜表（lyrics.md）", lyrics, "markdown")
text += block("当前的 storyboard.json", read(work / "storyboard.json"), "json")
text += block("当前的 graphics.py", read(work / "graphics.py"), "python")
text += block("画面文档（references/visuals.md）", read(REF / "visuals.md"), "markdown")
out.write_text(text + "\n", encoding="utf-8")
print(report)
print(f"\n已生成 {out}")
if sheet_ok:
    print("预览图已生成：作品目录里的 分镜预览_p1.jpg …（每页 6 句）。把它们和上面的文件一起发给聊天 AI，也自己看一遍。")
    print("没有问题就可以出片：python mrv.py render <作品目录>")
else:
    print("检查没有通过，所以还没有预览图。把上面的文件发给聊天 AI，按它改好的文件覆盖后再运行一次 fix。")
sys.exit(0 if r.returncode == 0 else 1)
