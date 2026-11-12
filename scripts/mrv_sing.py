"""歌词 → 「送唱版」：给音乐模型唱、给对齐用的那一份。

lyrics.md 是给人看、上屏的（可以写 3²、1/12、50%）；音乐模型看到阿拉伯数字和符号常常乱读，
所以唱的那份要写成汉字：3² → 三的平方、1/12 → 十二分之一、50% → 百分之五十、180° → 一百八十度。
还会：去掉圆括号（Suno 会把圆括号里的字唱成和声）、去掉引号书名号、按作品里的 读音替换.json 换掉多音字和生僻字。
两份句数、顺序完全一样，所以对齐用唱的那份，字幕照样显示 lyrics.md 的写法。
"""
import json
import re
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DIG = "零一二三四五六七八九"
POLY = "长行重量差得还着了调种数都为便乐曲少好处空角率降系藏朝解传弹参"   # 常见多音字：唱错了再加读音替换


def _sec(x):
    """0 < x < 10000 → 汉字（中间的零照规矩补）。"""
    s, zero = "", False
    for p, u in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
        d, x = divmod(x, p)
        if d == 0:
            if s:
                zero = True
            continue
        if zero:
            s += "零"
            zero = False
        s += DIG[d] + u
    return s


def int_zh(n):
    n = int(n)
    if n < 0:
        return "负" + int_zh(-n)
    if n == 0:
        return "零"
    yi, rest = divmod(n, 10 ** 8)
    wan, ge = divmod(rest, 10 ** 4)
    s = ""
    if yi:
        s += _sec(yi) + "亿"
    if wan:
        if yi and wan < 1000:
            s += "零"
        s += _sec(wan) + "万"
    if ge:
        if (yi or wan) and ge < 1000:
            s += "零"
        s += _sec(ge)
    s = s[1:] if s.startswith("一十") else s
    return re.sub(r"^二(?=[千万亿])", "两", s)   # 两千、两万更顺口


def num_zh(tok):
    if "." in tok:
        a, b = tok.split(".", 1)
        return int_zh(a or 0) + "点" + "".join(DIG[int(c)] for c in b)
    return int_zh(tok)


_SYM = [("≈", "约等于"), ("≠", "不等于"), ("≥", "大于等于"), ("≤", "小于等于"), ("×", "乘"), ("÷", "除以"),
        ("+", "加"), ("=", "等于"), (">", "大于"), ("<", "小于"), ("√", "根号"), ("π", "派"), ("∞", "无穷大"),
        ("²", "的平方"), ("³", "的立方"), ("°", "度")]
_NUM = r"\d+(?:\.\d+)?"


def sing_text(text, subs=None):
    s = text
    for k, v in sorted((subs or {}).items(), key=lambda kv: -len(kv[0])):
        s = s.replace(k, v)
    s = re.sub(r"[“”\"「」『』《》【】]", "", s)
    s = re.sub(r"[（）()]", "", s)
    s = re.sub(r"(?<=[A-Za-z0-9²³)])\s*[-−]\s*(?=[A-Za-z0-9(])", "减", s)   # 3-1、x-1：减
    s = re.sub(r"[-−](?=\d)", "负", s)                                         # 等于-1：负
    s = re.sub(rf"({_NUM})\s*%", lambda m: "百分之" + num_zh(m.group(1)), s)
    s = re.sub(r"(\d+)\s*/\s*(\d+)", lambda m: int_zh(m.group(2)) + "分之" + int_zh(m.group(1)), s)
    s = re.sub(_NUM, lambda m: num_zh(m.group(0)), s)
    for a, b in _SYM:
        s = s.replace(a, b)
    s = s.replace("*", "乘")
    return re.sub(r"\s+", " ", s).strip()


def parse_lyrics(path):
    """读 lyrics.md：返回 (头信息 dict, 段落 [{name, lines:[(句号, 歌词)]}])。遇到不带 [ ] 的 ## 小节（比如分镜表）就停。"""
    meta, sections = {}, []
    for raw in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line.startswith("# ") and "title" not in meta:
            meta["title"] = line[2:].strip()
            continue
        m = re.match(r"-\s*(bpm|口诀)\s*[:：]\s*\**(.+?)\**\s*$", line, re.I)
        if m and not sections:
            meta[m.group(1).lower()] = m.group(2).strip()
            continue
        if line.startswith("## "):
            m = re.match(r"##\s*\[(.+?)\]", line)
            if not m:
                if sections:
                    break
                continue
            sections.append({"name": m.group(1).strip(), "lines": []})
            continue
        m = re.match(r"(\d+)[\.、]\s*(.+)", line)
        if m and sections:
            sections[-1]["lines"].append((int(m.group(1)), m.group(2).strip()))
    return meta, sections


def is_hook(name):
    return bool(re.search(r"hook|chorus|副歌|口诀", name, re.I))


def lyrics_block(sections, sung, fmt, bpm):
    """按平台排歌词：suno / plain / mureka。"""
    out = []
    if fmt == "suno":
        out += ["[Intro - 2 bars, drums and piano only]", ""]
    elif fmt == "mureka":
        out += ["[Intro]", ""]
    for sec in sections:
        name = sec["name"]
        if is_hook(name):
            tag = {"suno": "[Hook - emphasized, every word clear]", "mureka": "[Chorus]"}.get(fmt, "[Hook]")
        else:
            base = re.sub(r"\s.*$", "", name) if re.match(r"(?i)verse|intro|outro|bridge", name) else name
            if fmt != "plain" and not re.match(r"(?i)verse|intro|outro|bridge|pre", base):
                base = "Verse"
            tag = f"[{base}]"
            m = re.match(r"(?i)(verse)\s*(\d+)", name)
            if m:
                tag = f"[Verse {m.group(2)}]"
        out.append(tag)
        out += [sung[n] for n, _ in sec["lines"]]
        out.append("")
    if fmt == "suno":
        out += ["[Outro - 2 bars, instrumental]", "[End]"]
    elif fmt == "mureka":
        out += ["[Outro]"]
    return "\n".join(out).strip()


def build(work, bpm=None):
    """写出 唱词.md（对齐用）和 给音乐模型/ 里各平台的提示词。返回报告文字列表。"""
    work = Path(work)
    lp = next((work / n for n in ("lyrics.md", "歌词.md") if (work / n).exists()), None)
    if lp is None:
        raise SystemExit(f"错误：{work} 里没有 lyrics.md。先按 prompts/写词.md 让 AI 写歌词，存成 lyrics.md")
    meta, sections = parse_lyrics(lp)
    if not sections or not any(s["lines"] for s in sections):
        raise SystemExit(f"错误：{lp.name} 里没有读到歌词。格式：'## [Verse 1]' 下面一行一句 '1. 歌词'")
    subs_p = work / "读音替换.json"
    subs = json.loads(subs_p.read_text(encoding="utf-8")) if subs_p.exists() else {}
    bpm = float(bpm or meta.get("bpm") or 90)
    nums = [n for s in sections for n, _ in s["lines"]]
    if nums != list(range(1, len(nums) + 1)):
        raise SystemExit(f"错误：歌词句号要从 1 连续编到最后（现在是 {nums[:6]}…），换段也不要重新编号")
    shown = {n: t for s in sections for n, t in s["lines"]}
    sung = {n: sing_text(t, subs) for n, t in shown.items()}
    report = []
    changed = [(n, shown[n], sung[n]) for n in nums if shown[n].replace("（", "").replace("）", "") != sung[n]]
    latin = [(n, sung[n]) for n in nums if re.search(r"[A-Za-z]", sung[n])]
    poly = sorted({c for n in nums for c in shown[n] if c in POLY})

    md = [f"# {meta.get('title', work.name)}（送唱版：给音乐模型唱、给对齐用；mrv.py lyrics 自动生成，别手改）", ""]
    for sec in sections:
        md.append(f"## [{sec['name']}]")
        md += [f"{n}. {sung[n]}" for n, _ in sec["lines"]]
        md.append("")
    (work / "唱词.md").write_text("\n".join(md), encoding="utf-8")

    out_dir = work / "给音乐模型"
    out_dir.mkdir(exist_ok=True)
    fill = {"{{bpm}}": f"{bpm:g}", "{{bpm_lo}}": f"{bpm - 2:g}", "{{bpm_hi}}": f"{bpm + 2:g}",
            "{{intro_sec}}": f"{2 * 240 / bpm:.1f}", "{{n_lines}}": str(len(nums)),
            "{{lyrics_suno}}": lyrics_block(sections, sung, "suno", bpm),
            "{{lyrics_plain}}": lyrics_block(sections, sung, "plain", bpm),
            "{{lyrics_mureka}}": lyrics_block(sections, sung, "mureka", bpm)}
    (out_dir / "送唱版歌词.txt").write_text(fill["{{lyrics_plain}}"] + "\n", encoding="utf-8")
    for tpl in sorted((SKILL / "prompts" / "音乐模型").glob("*.md")):
        s = tpl.read_text(encoding="utf-8")
        for k, v in fill.items():
            s = s.replace(k, v)
        (out_dir / tpl.name).write_text(s, encoding="utf-8")

    report.append(f"送唱版写好了：{len(nums)} 句，{bpm:g} BPM → 唱词.md、给音乐模型/（{'、'.join(p.stem for p in sorted(out_dir.glob('*.md')))}）")
    if changed:
        report.append("这几句唱的写法和字幕不一样（数字、符号换成了汉字）：")
        report += [f"  第 {n} 句：{a} → {b}" for n, a, b in changed[:12]]
    if latin:
        report.append("这几句还有英文字母，音乐模型可能按英文读；要读中文就在 读音替换.json 里写读法（例：{\"a²\": \"A的平方\"}）：")
        report += [f"  第 {n} 句：{t}" for n, t in latin[:8]]
    if poly:
        report.append(f"歌词里有多音字 {'、'.join(poly)}：生成后听一下，唱错了就在 读音替换.json 里换成同音的常用字（只影响唱的那份）")
    return report


if __name__ == "__main__":
    import sys
    for line in build(sys.argv[1] if len(sys.argv) > 1 else "."):
        print(line)
