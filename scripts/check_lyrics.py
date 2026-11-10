"""歌词体检：交给用户确认、交给客户做音频之前运行。检查结构、每句字数、押韵、容易听错的写法。
用法: python check_lyrics.py <作品目录或歌词文件> [--bpm 90]
只报告问题，不改文件。"必须改"的问题存在时退出码为 1；"建议"不影响退出码。
"""
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0)
target = Path(sys.argv[1])
bpm = float(sys.argv[sys.argv.index("--bpm") + 1]) if "--bpm" in sys.argv else 90.0
if target.is_dir():
    target = next((target / n for n in ("lyrics.md", "歌词.md", "lyrics.txt") if (target / n).exists()), target / "lyrics.md")
if not target.exists():
    sys.exit(f"找不到歌词文件 {target}")

sections, cur = [], None
for raw in target.read_text(encoding="utf-8-sig").splitlines():
    m = re.match(r"\s*##\s*\[(.+?)\]", raw)
    if m:
        cur = {"name": m.group(1), "lines": []}
        sections.append(cur)
        continue
    m = re.match(r"\s*(\d+)[\.、]\s*(.+)", raw)
    if m:
        if cur is None:
            cur = {"name": "（未分段）", "lines": []}
            sections.append(cur)
        cur["lines"].append((int(m.group(1)), m.group(2).strip()))

must, advice = [], []
lines = [(n, t, s["name"]) for s in sections for n, t in s["lines"]]
if not lines:
    sys.exit("没有读到歌词行。格式：'## [Verse 1]' 开段，'1. 歌词' 每句一行")


def units(text):
    """可唱的字数：一个汉字算 1，一串英文或数字算 1 个词（so easy = 2）。"""
    cjk = len(re.findall(r"[一-鿿]", text))
    words = len(re.findall(r"[A-Za-z]+|\d+", text))
    return cjk + words


# 编号连续
nums = [n for n, _, _ in lines]
if nums != list(range(1, len(nums) + 1)):
    must.append(f"句子编号要从 1 连续到 {len(nums)}（现在是 {nums[:6]}…）。分镜里的 L(6)、W(9,'字') 靠编号定位")
if any("【" in t for _, t, _ in lines):
    must.append("还有没填的模板占位符【…】")

# 结构
hook = [s for s in sections if "hook" in s["name"].lower()]
if not hook:
    advice.append("没有 [Hook] 段。建议口诀第二次出现时单独成段（2 句），夹在长句里容易唱糊")
else:
    if len(hook[0]["lines"]) < 2:
        must.append("[Hook] 段至少 2 句（一段音频太短，音乐平台排不稳）")
    if hook[0]["lines"] and units(hook[0]["lines"][0][1]) > 10:
        advice.append(f"[Hook] 第一句应只有口诀本身（≤10 字），现在 {units(hook[0]['lines'][0][1])} 字")
for s in sections:
    if len(s["lines"]) == 1:
        must.append(f"[{s['name']}] 只有 1 句，至少 2 句")
if not 16 <= len(lines) <= 32:
    advice.append(f"共 {len(lines)} 句。常用的是 24 句（约 64 秒）；少于 16 句讲不清，多于 32 句太长")

# 字数
last_sec = sections[-1]["name"] if len(sections) > 1 else None
for n, t, sec in lines:
    u = units(t)
    is_hook = "hook" in sec.lower()
    if u > 16:
        must.append(f"第 {n} 句 {u} 字，一小节唱不下（上限 15–16）：{t}")
    elif u > 15:
        advice.append(f"第 {n} 句 {u} 字，偏满，容易唱得赶：{t}")
    elif u < 7 and not is_hook:
        advice.append(f"第 {n} 句只有 {u} 字，一小节会显得空：{t}")
    elif sec == last_sec and not is_hook and u > 12:
        advice.append(f"第 {n} 句 {u} 字。最后一段（讲原理）建议每句 9–11 字，留出气口：{t}")

# 容易听错的写法
for n, t, _ in lines:
    for pat, why in [(r"是四|是十|四是|十是", "“是/四/十”连在一起容易听混"),
                     (r"[一二三四五六七八九十百]{6,}", "连续 6 个以上数字，唱不清")]:
        if re.search(pat, t):
            advice.append(f"第 {n} 句：{why}：{t}")

# 押韵
try:
    from pypinyin import Style, lazy_pinyin

    GROUPS = [("i/ü", {"i", "v", "u:", "er", "ü"}), ("a", {"a", "ia", "ua"}), ("o/e", {"o", "e", "uo", "ie", "ve", "ue"}),
              ("ai", {"ai", "uai"}), ("ei", {"ei", "uei", "ui"}), ("ao", {"ao", "iao"}), ("ou", {"ou", "iou", "iu"}),
              ("an", {"an", "ian", "uan", "van"}), ("en/in", {"en", "in", "uen", "un", "vn"}),
              ("ang", {"ang", "iang", "uang"}), ("eng/ing", {"eng", "ing", "ueng", "ong", "iong"}), ("u", {"u"})]

    def group(line_text):
        # 整句一起注音再取最后一个字，多音字才读得对（"顶呱呱"的"呱"读 guā 不是 gū）
        cjk_only = "".join(re.findall(r"[一-鿿]", line_text))
        f = lazy_pinyin(cjk_only, style=Style.FINALS, strict=False)[-1]
        ini = lazy_pinyin(cjk_only, style=Style.INITIALS, strict=False)[-1]
        if f == "i" and ini in ("z", "c", "s", "zh", "ch", "sh", "r"):
            return "i/ü"  # 资、知 这类也归到 i 韵，口语里听感接近
        if f == "u" and ini in ("j", "q", "x", "y"):
            return "i/ü"
        return next((g for g, fs in GROUPS if f in fs), f)

    tails = []
    for n, t, _ in lines:
        cj = re.findall(r"[一-鿿]", t)
        last_word = re.findall(r"[A-Za-z]+\s*$", t)
        tails.append((n, t, "英文" if last_word else (group(t) if cj else "?")))
    counts = {}
    for _, _, g in tails:
        if g != "英文":
            counts[g] = counts.get(g, 0) + 1
    main, cnt = max(counts.items(), key=lambda kv: kv[1])
    off = [(n, t, g) for n, t, g in tails if g not in (main, "英文")]
    rate = cnt / max(1, sum(counts.values()))
    rhyme_note = f"主韵 {main}，{cnt}/{sum(counts.values())} 句押上"
    if rate < 0.7:
        advice.append(f"押韵不够整齐（{rhyme_note}）。没押上的句尾：" + "；".join(f"{n}「{t[-3:]}」({g})" for n, t, g in off[:8]))
    elif off:
        rhyme_note += "；没押上：" + "、".join(f"第{n}句" for n, _, _ in off)
except ImportError:
    rhyme_note = "没有安装 pypinyin，跳过押韵检查（pip install pypinyin）"

bar = 4 * 60 / bpm
print(f"歌词文件：{target.name}　共 {len(lines)} 句，{len(sections)} 段：" + "、".join(f"[{s['name']}] {len(s['lines'])} 句" for s in sections))
print(f"按 {bpm:g} BPM、一句一小节估算：人声约 {len(lines) * bar:.0f} 秒")
us = [units(t) for _, t, _ in lines]
print(f"每句字数：最少 {min(us)}，最多 {max(us)}，平均 {sum(us) / len(us):.1f}")
print("押韵：" + rhyme_note)
for m in must:
    print("【必须改】", m)
for a in advice:
    print("【建议】  ", a)
if not must and not advice:
    print("没有发现问题。")
print("提醒：例题里的每个数字要自己再验算一遍，脚本查不了数学对不对。")
sys.exit(1 if must else 0)
