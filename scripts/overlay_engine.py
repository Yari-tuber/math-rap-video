"""叠加层渲染引擎：画口诀横幅、字幕、公式、弹字、箭头；题目专用图形由作品目录的 graphics.py 提供。

所有时间都是"音频时间"（秒）。分镜里的时间可以写数字，但推荐写成相对歌词的表达式，这样换音频不用改：
    L(6)            第 6 句的起点          E(6)   第 6 句的终点
    W(9,"四")       第 9 句里"四"字唱出来的时间；W(9,"四",2) 表示第 2 个"四"
    C(9,3)          第 9 句第 3 个字的时间
    B               一拍的长度；beat(k) 第 k 拍的时间
    T0 / T_END      成片起止
  例："L(6)+2*B"、"W(10,'十')"、"E(14)-0.2"
时间数据来自 timing.json（prepare_audio.py 生成）。

用法:
    python overlay_engine.py <作品目录> check                  # 检查时间写法、全片试画、版面碰撞提醒
    python overlay_engine.py <作品目录> sheet [--at 0.5]        # 每句一格的总览 → 分镜预览.jpg（默认取每句快唱完时；--at 取句内比例）
    python overlay_engine.py <作品目录> sheet --pages           # 再加大图分页（每页 6 格、每格 960×540）→ 分镜预览_p1.jpg …，用来看文字有没有压边
    python overlay_engine.py <作品目录> frames <起> <止> [步长]   # 一段时间内逐帧排开 → 分镜逐帧.jpg，用来看动画途中有没有碰撞
    python overlay_engine.py <作品目录> png <时间> [...]         # 单帧预览（深色底）；pnga 输出透明底
    python overlay_engine.py <作品目录> info [表达式...]         # 输出 JSON：t0、t_end、每句时间、表达式的值
    python overlay_engine.py <作品目录> raw [起 止]              # RGBA 原始帧写到 stdout（build_video.py 用）
    python overlay_engine.py <作品目录> cover <时间> [...]       # 各时间点图形占画面的比例（build_video.py 挑背景用）
"""
import importlib.util
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw, ImageFont

for _s in (sys.stdout, sys.stderr):  # 系统编码不支持中文时也不要崩
    try:
        _s.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass

if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0)
WORK = Path(sys.argv[1]).resolve()
MODE = sys.argv[2] if len(sys.argv) > 2 else "raw"


def _die(msg):
    print("错误：" + msg, file=sys.stderr)
    sys.exit(2)


if not (WORK / "storyboard.json").exists():
    _die(f"{WORK} 里没有 storyboard.json")
SB = json.loads((WORK / "storyboard.json").read_text(encoding="utf-8"))
_tp = WORK / SB.get("timing", "timing.json")
if not _tp.exists():
    _die(f"找不到 {_tp.name}：先运行 prepare_audio.py 处理音频")
TM = json.loads(_tp.read_text(encoding="utf-8"))

WIDTH, HEIGHT = 1920, 1080
FPS = SB.get("fps", 30)
S = SB.get("supersample", 2)
BPM = SB.get("bpm", TM["bpm"])
BEAT = 60 / BPM
BEAT0 = SB.get("beat0", TM["beat0"])
LINES = [(l["start"], l["end"], l["text"]) for l in TM["lines"]]
_CT = [l.get("ct") for l in TM["lines"]]
NL = len(LINES)
SONG = SB.get("song", TM["audio"])


# ---------------- 时间函数 ----------------
def _line(i):
    if not (isinstance(i, int) and 1 <= i <= NL):
        raise ValueError(f"句号 {i} 超出范围（共 {NL} 句）")
    return i - 1


def L(i):
    return LINES[_line(i)][0]


def E(i):
    return LINES[_line(i)][1]


def C(i, k):
    s, e, text = LINES[_line(i)]
    if not 1 <= k <= len(text):
        raise ValueError(f"第 {i} 句「{text}」只有 {len(text)} 个字，取不到第 {k} 个")
    ct = _CT[i - 1]
    return ct[k - 1] if ct else s + (e - s) * (k - 1) / len(text)


def W(i, s, n=1):
    text = LINES[_line(i)][2]
    pos = -1
    for _ in range(n):
        pos = text.find(s, pos + 1)
        if pos < 0:
            raise ValueError(f"第 {i} 句「{text}」里找不到第 {n} 个「{s}」")
    return C(i, pos + 1)


def beat(k):
    return BEAT0 + k * BEAT


_NS = {"L": L, "E": E, "C": C, "W": W, "B": BEAT, "beat": beat, "NL": NL, "min": min, "max": max,
       "__builtins__": {}}
T0 = TM["t0"]
T_END = TM["t_end"]
_NS.update(T0=T0, T_END=T_END)


def tm(x, where=""):
    """时间表达式 → 秒。出错时指出是哪一项。"""
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(eval(str(x), _NS))
    except Exception as e:  # noqa: BLE001
        _die(f"时间写法有问题 {where}：{x!r} → {e}")


if "t0" in SB:
    T0 = tm(SB["t0"], "t0")
if "t_end" in SB:
    T_END = tm(SB["t_end"], "t_end")
_NS.update(T0=T0, T_END=T_END)

# ---------------- 颜色 / 字体 ----------------
COLORS = {
    "white": (255, 255, 255, 255), "yellow": (255, 216, 74, 255), "red": (236, 84, 106, 255),
    "blue": (76, 141, 255, 255), "blue_dark": (40, 92, 200, 255), "blue_light": (130, 185, 255, 255),
    "gray": (150, 150, 160, 255), "orange": (255, 96, 48, 255), "line": (230, 236, 255, 255),
    "green": (92, 214, 140, 255),
}
COLORS.update({k: tuple(v) for k, v in SB.get("colors", {}).items()})


def col(c):
    if c is None:
        return None
    if isinstance(c, str):
        if c not in COLORS:
            _die(f"没有这个颜色名：{c}（可用：{', '.join(COLORS)}，或写 [r,g,b]）")
        return COLORS[c]
    c = tuple(c)
    return c if len(c) == 4 else c + (255,)


def _first_font(cands, what):
    for c in cands:
        if Path(c).exists():
            return str(c)
    _die(f"找不到{what}字体。在 storyboard.json 里加 \"fonts\": {{\"heavy\": [\"字体文件路径\"], \"subtitle\": [...]}}，"
         f"需要支持中文的粗体。已找过：{cands}")


_skill_fonts = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_bundled = sorted(str(p) for p in _skill_fonts.glob("*.[to]t[fc]")) if _skill_fonts.exists() else []
_fonts = SB.get("fonts", {})
FONT_HEAVY = _first_font(_fonts.get("heavy", []) + _bundled + [
    "C:/Windows/Fonts/NotoSansSC-VF.ttf", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"], "标题")
FONT_SUB = _first_font(_fonts.get("subtitle", []) + [
    "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/NotoSansSC-VF.ttf", "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"] + _bundled,
    "字幕")


# ---------------- 动画工具 ----------------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x):
    x = clamp(x)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def lerp(a, b, p):
    """数或坐标点的插值（p 会被限制在 0–1）。"""
    p = clamp(p)
    if isinstance(a, (int, float)):
        return a + (b - a) * p
    return tuple(x + (y - x) * p for x, y in zip(a, b))


def fade(t, t_in, t_out=None, d=0.15):
    a = clamp((t - t_in) / d)
    if t_out is not None:
        a *= clamp((t_out - t) / d)
    return a


def pop(t, t0, dur=0.22):
    """回弹出现：返回 (缩放, 透明度)；t0 之前是 (0, 0)。"""
    if t < t0:
        return 0, 0
    p = (t - t0) / dur
    return 0.6 + 0.4 * ease_back(p), clamp(p * 1.8)


def polar(cx, cy, r, deg):
    """从 (cx,cy) 出发、方向 deg 度、距离 r 的点。角度按数学习惯：0° 向右，逆时针为正（90° 向上）。"""
    a = math.radians(deg)
    return (cx + r * math.cos(a), cy - r * math.sin(a))


def rotate(pts, center, deg):
    """把一组点绕 center 逆时针转 deg 度（整块图形旋转）。"""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = center
    return [(cx + (x - cx) * ca + (y - cy) * sa, cy - (x - cx) * sa + (y - cy) * ca) for x, y in pts]


def shift(pts, dx, dy):
    """把一组点平移。"""
    return [(x + dx, y + dy) for x, y in pts]


def spread(n, x0=240, x1=1680):
    """把 n 个元素在 x0–x1 之间等距排开，返回每个元素的中心 x。默认铺满画面宽度（两边各留 240）。"""
    if n <= 1:
        return [(x0 + x1) / 2]
    return [x0 + k * (x1 - x0) / (n - 1) for k in range(n)]


def along(path, p):
    """沿折线 path 匀速走到比例 p（0–1）处的点。用来让图形沿路线移动。"""
    p = clamp(p)
    seg = [math.dist(a, b) for a, b in zip(path, path[1:])]
    d = p * sum(seg)
    for k, L_ in enumerate(seg):
        if d <= L_ or k == len(seg) - 1:
            return lerp(path[k], path[k + 1], d / L_ if L_ else 0)
        d -= L_
    return path[-1]


def red_then(t, t0, hold=0.45, first="red", then="blue"):
    """刚出现时用强调色 first，hold 秒后变成 then（"先红后蓝"）。"""
    return first if t < t0 + hold else then


def beat_flash(t, start, end=None, width=0.2):
    """在 [start, end) 内，每拍开头 width 比例的时间返回 True（跟拍闪烁）。"""
    if t < start or (end is not None and t >= end):
        return False
    return ((t - BEAT0) / BEAT) % 1 < width


@lru_cache(maxsize=64)
def font(path, size, weight=None):
    f = ImageFont.truetype(path, int(size * S))
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:  # noqa: BLE001  非可变字体没有字重轴
            pass
    return f


_TRACK = {"on": False, "bbox": None}


@lru_cache(maxsize=512)
def text_img(text, size, color=(255, 255, 255, 255), path=None, weight=900, stroke=0,
             stroke_color=(0, 0, 0, 255)):
    """把文字渲染成 S 倍尺寸的 RGBA 小图（有缓存）。"""
    path = path or FONT_HEAVY
    f = font(path, size, weight)
    sw = int(stroke * S)
    bbox = f.getbbox(text, stroke_width=sw)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    im = Image.new("RGBA", (w + 4 * S, h + 4 * S), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((-bbox[0] + 2 * S, -bbox[1] + 2 * S), text, font=f, fill=col(color),
                            stroke_width=sw, stroke_fill=stroke_color)
    return im


def text_width(text, size, weight=900, stroke=0):
    """文字按 1920×1080 坐标的宽度（排版、对齐用）。"""
    return text_img(str(text), size, (255, 255, 255, 255), FONT_HEAVY, weight, stroke=stroke).width / S


_TEXTS = []          # check 时记录这一帧里每块文字的外框：(文字, x0, y0, x1, y1)


def _note_text(label, im, cx, cy, scale=1.0, alpha=1.0, anchor="c", size=99):
    """check 模式下记下一块文字占的位置，用来发现文字互相压住。半透明或正在弹出的不记。"""
    if not _TRACK["on"] or alpha < 0.6 or scale < 0.6 or not str(label).strip():
        return
    w, h = im.width / S * scale, im.height / S * scale
    x0 = cx - (w / 2 if anchor[0] == "c" else 0 if anchor[0] == "l" else w)
    _TEXTS.append((str(label), x0, cy - h / 2, x0 + w, cy + h / 2, size * scale))


def put(canvas, im, cx, cy, scale=1.0, alpha=1.0, anchor="c"):
    """把 S 倍尺寸的小图贴到画布，cx/cy 是 1920×1080 坐标；anchor: c 居中 / l 左对齐 / r 右对齐。"""
    if alpha <= 0.003 or scale <= 0.01:
        return
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if alpha < 0.999:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    x = int(cx * S - (im.width / 2 if anchor[0] == "c" else 0 if anchor[0] == "l" else im.width))
    y = int(cy * S - im.height / 2)
    canvas.alpha_composite(im, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))


def new_layer():
    return Image.new("RGBA", (WIDTH * S, HEIGHT * S), (0, 0, 0, 0))


def composite(canvas, layer, alpha=1.0):
    if alpha <= 0.003:
        return
    if alpha < 0.999:
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    canvas.alpha_composite(layer)


class Stage:
    """画图形用的图层。所有坐标、半径、线宽都按 1920×1080 写，内部自动换算和取整。
    用法： st = ctx.stage(); st.line(...); st.dot(...); st.text(...); st.commit(canvas, alpha)"""

    def __init__(self):
        self.layer = new_layer()
        self.d = ImageDraw.Draw(self.layer)

    @staticmethod
    def _w(width):
        return max(1, int(round(width * S)))

    @staticmethod
    def _p(pts):
        return [(x * S, y * S) for x, y in pts]

    def _blend(self, pts_s, painter, pad=0):
        """半透明填充：先画到一张小图再混合上去（直接画会把下面的内容盖掉，而不是透出来）。"""
        xs = [x for x, _ in pts_s]
        ys = [y for _, y in pts_s]
        x0, y0 = max(0, int(min(xs)) - pad - 2), max(0, int(min(ys)) - pad - 2)
        x1, y1 = min(WIDTH * S, int(max(xs)) + pad + 3), min(HEIGHT * S, int(max(ys)) + pad + 3)
        if x1 <= x0 or y1 <= y0:
            return
        tmp = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        painter(ImageDraw.Draw(tmp), [(x - x0, y - y0) for x, y in pts_s])
        self.layer.alpha_composite(tmp, (x0, y0))

    def _fill(self, pts_s, painter, fill, pad=0):
        if fill is not None and fill[3] < 255:
            self._blend(pts_s, painter, pad)
        else:
            painter(self.d, pts_s)

    def line(self, pts, color="line", width=9, curve=False, prog=1.0):
        """折线 / 线段。pts=[(x,y),...]；curve=True 拐角圆滑；prog<1 只画前面一部分（按长度）。"""
        if prog <= 0 or len(pts) < 2:
            return
        if prog < 1:
            seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
            d, out = clamp(prog) * sum(seg), [pts[0]]
            for k, L_ in enumerate(seg):
                if d >= L_:
                    out.append(pts[k + 1])
                    d -= L_
                else:
                    out.append(lerp(pts[k], pts[k + 1], d / L_ if L_ else 0))
                    break
            pts = out
        if len(pts) >= 2:
            self.d.line(self._p(pts), fill=col(color), width=self._w(width), joint="curve" if curve else None)

    def dashed(self, pts, color="gray", width=7, on=3, step=4):
        """虚线：pts 要足够密（比如弧线的采样点）。"""
        p = self._p(pts)
        for i in range(0, len(p) - 1, step):
            self.d.line(p[i:i + on], fill=col(color), width=self._w(width), joint="curve")

    def dot(self, x, y, r, fill="white", outline=None, width=0):
        f, o, w = col(fill), col(outline), (self._w(width) if outline else 0)
        self._fill(self._p([(x - r, y - r), (x + r, y + r)]),
                   lambda d, q: d.ellipse([q[0], q[1]], fill=f, outline=o, width=w), f, w)

    def ring(self, x, y, r, color="red", width=8):
        self.d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], outline=col(color), width=self._w(width))

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0, radius=0):
        f, o, w = col(fill), col(outline), (self._w(width) if outline else 0)
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)

        def paint(d, q):
            if radius:
                d.rounded_rectangle([q[0], q[1]], radius=int(radius * S), fill=f, outline=o, width=w)
            else:
                d.rectangle([q[0], q[1]], fill=f, outline=o, width=w)
        self._fill(self._p([(x0, y0), (x1, y1)]), paint, f, w)

    def poly(self, pts, fill=None, outline=None, width=0):
        f, o, w = col(fill), col(outline), (self._w(width) if outline else 0)
        self._fill(self._p(pts), lambda d, q: d.polygon(q, fill=f, outline=o, width=w), f, w)

    def wedge(self, cx, cy, r, a0, a1, fill="yellow", outline=None, width=0):
        """扇形（画一个角）。顶点 (cx,cy)，半径 r，从 a0 度到 a1 度；0° 向右，逆时针为正。"""
        f, o, w = col(fill), col(outline), (self._w(width) if outline else 0)
        lo, hi = min(a0, a1), max(a0, a1)
        self._fill(self._p([(cx - r, cy - r), (cx + r, cy + r)]),
                   lambda d, q: d.pieslice([q[0], q[1]], -hi, -lo, fill=f, outline=o, width=w), f, w)

    def angle_arc(self, cx, cy, r, a0, a1, color="white", width=6):
        """角的弧线标记（不填充）。角度约定同 wedge。"""
        lo, hi = min(a0, a1), max(a0, a1)
        self.d.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], -hi, -lo, fill=col(color),
                   width=self._w(width))

    def right_angle(self, cx, cy, size, a0, color="white", width=5):
        """直角符号：顶点 (cx,cy)，一条边朝 a0 度方向，另一条边朝 a0+90 度。"""
        p1, p3 = polar(cx, cy, size, a0), polar(cx, cy, size, a0 + 90)
        p2 = (p1[0] + p3[0] - cx, p1[1] + p3[1] - cy)
        self.line([p1, p2, p3], color, width)

    def tile(self, x, y, w, h, text="", fill="blue", text_color="white", size=None, radius=10, outline="white",
             width=3, scale=1.0, alpha=1.0):
        """带文字的圆角方块（数字格子），以 (x,y) 为中心；scale 可配合 ctx.pop 做弹出。"""
        if scale <= 0.01 or alpha <= 0.003:
            return
        w2, h2 = w * scale / 2, h * scale / 2
        f = col(fill)
        if f is not None and alpha < 0.999:
            f = f[:3] + (int(f[3] * alpha),)
        self.rect(x - w2, y - h2, x + w2, y + h2, f, outline if alpha > 0.5 else None, width, radius * scale)
        if text != "":
            self.text(text, x, y, size or h * 0.55, text_color, 800, scale=scale, alpha=alpha)

    def stack(self, x, y_bottom, w, unit_h, n, fill="blue", outline="white", width=3, gap=0, label="", label_size=40,
              label_color="white", alpha=1.0):
        """一摞 n 个单位方格（台阶、柱状、数方块）：以 x 为中心，从 y_bottom 往上摞，每格宽 w、高 unit_h。
        label 写在柱子正下方。返回柱子顶部的 y，方便在上面再标数字。"""
        f = col(fill)
        if f is not None and alpha < 0.999:
            f = f[:3] + (int(f[3] * alpha),)
        for k in range(int(n)):
            y1 = y_bottom - k * (unit_h + gap)
            self.rect(x - w / 2, y1 - unit_h, x + w / 2, y1, f, outline if alpha > 0.5 else None, width, 0)
        if label != "":
            self.text(label, x, y_bottom + label_size * 0.8, label_size, label_color, 800, stroke=2, alpha=alpha)
        return y_bottom - int(n) * (unit_h + gap)

    def brace(self, x0, x1, y, label="", color="white", size=40, below=True, width=4, tick=14, label_color=None,
              alpha=1.0):
        """水平括线：从 x0 到 x1 的一条线，两端带小竖线，中间配说明文字（below=True 文字在线下方）。"""
        k = 1 if below else -1
        c = col(color)
        if alpha < 0.999:
            c = c[:3] + (int(c[3] * alpha),)
        self.line([(x0, y - k * tick), (x0, y), (x1, y), (x1, y - k * tick)], c, width)
        if label:
            self.text(label, (x0 + x1) / 2, y + k * (size * 0.85), size, label_color or color, 800, stroke=2, alpha=alpha)

    def brace_v(self, x, y0, y1, label="", color="white", size=40, left=True, width=4, tick=14, label_color=None,
                alpha=1.0):
        """竖直括线：从 y0 到 y1，说明文字在左侧（left=True）或右侧。"""
        k = 1 if left else -1
        c = col(color)
        if alpha < 0.999:
            c = c[:3] + (int(c[3] * alpha),)
        self.line([(x + k * tick, y0), (x, y0), (x, y1), (x + k * tick, y1)], c, width)
        if label:
            self.text(label, x - k * 18, (y0 + y1) / 2, size, label_color or color, 800, stroke=2, alpha=alpha,
                      anchor="r" if left else "l")

    def tokens(self, toks, x, y, t, alpha=1.0, stroke=2, anchor="c"):
        """一行多段文字，各段有自己的颜色、字号和出现时间，整行按完整宽度对齐。
        toks = [(文字, 颜色, 字号, 出现时间秒), …]；时间用 ctx.L / ctx.W 算好再传进来。"""
        draw_token_row(self.layer, [(a, col(b), c, d) for a, b, c, d in toks], x, y, t, alpha, stroke, anchor)

    def arc_points(self, xa, xb, y, height, prog=1.0, below=False):
        """从 (xa,y) 到 (xb,y) 的半椭圆弧的采样点；prog 是画出来的比例（0–1）。"""
        prog = clamp(prog)
        rx, cx = (xb - xa) / 2, (xa + xb) / 2
        n = max(8, int(60 * prog))
        return [(cx - rx * math.cos(math.pi * prog * i / n),
                 y + (height if below else -height) * math.sin(math.pi * prog * i / n)) for i in range(n + 1)]

    def arc(self, xa, xb, y, height, prog=1.0, color="blue", width=11, below=False, dashed=False):
        if prog <= 0:
            return
        pts = self.arc_points(xa, xb, y, height, prog, below)
        if dashed:
            self.dashed(pts, color, width)
        else:
            self.line(pts, color, width, curve=True)

    def text(self, s, x, y, size, color="white", weight=900, stroke=0, scale=1.0, alpha=1.0, anchor="c",
             rotate=0):
        im = text_img(str(s), size, col(color), FONT_HEAVY, weight, stroke=stroke)
        if rotate:
            im = im.rotate(rotate, expand=True, resample=Image.BICUBIC)
        _note_text(s, im, x, y, scale, alpha, anchor, size)
        put(self.layer, im, x, y, scale, alpha, anchor)

    def image(self, im, x, y, scale=1.0, alpha=1.0, anchor="c"):
        put(self.layer, im, x, y, scale, alpha, anchor)

    def commit(self, canvas, alpha=1.0):
        composite(canvas, self.layer, alpha)


# ---------------- 通用图层（读 storyboard.json） ----------------
_banner = SB.get("banner")
if _banner:
    _banner = dict(_banner, parts=[(p, tm(tp, f"banner.parts「{p}」")) for p, tp in _banner["parts"]],
                   pulses=[tm(x, "banner.pulses") for x in _banner.get("pulses", [])])
_formulas = []
for n, f in enumerate(SB.get("formulas", [])):
    w = f"formulas[{n}]"
    _formulas.append((tm(f["show"], w + ".show"), tm(f["hide"], w + ".hide"),
                      [(tk[0], col(tk[1]), tk[2], tm(tk[3], f"{w}「{tk[0]}」")) for tk in f["tokens"]],
                      f.get("y", 830)))
_keywords = []
for n, k in enumerate(SB.get("keywords", [])):
    w = f"keywords[{n}]「{k.get('text')}」"
    _keywords.append(dict(k, show=tm(k["show"], w), pop=tm(k.get("pop", k["show"]), w), hide=tm(k["hide"], w)))
_arrows = [dict(a, show=tm(a["show"], f"arrows[{n}]"), hide=tm(a["hide"], f"arrows[{n}]"))
           for n, a in enumerate(SB.get("arrows", []))]
_sub = SB.get("subtitles", {})


def draw_banner(canvas, t):
    if not _banner or t < _banner["parts"][0][1]:
        return
    pulse = 1.0
    for tp in _banner["pulses"]:
        if tp <= t < tp + 0.35:
            pulse = 1 + 0.12 * math.sin(math.pi * (t - tp) / 0.35)
    size = _banner.get("size", 84)
    ims = [text_img(p, size, (255, 255, 255, 255), FONT_HEAVY, 900, stroke=3) for p, _ in _banner["parts"]]
    total = sum(im.width for im in ims) / S
    x = 960 - total / 2 * pulse
    for (p, tp), im in zip(_banner["parts"], ims):
        sc, al = pop(t, tp, 0.2)
        w = im.width / S * pulse
        put(canvas, im, x + w / 2, _banner.get("y", 78), sc * pulse, al)
        x += w


def draw_token_row(canvas, toks, cx, y, t, alpha=1.0, stroke=2, anchor="c"):
    ims = [text_img(tx, sz, c, FONT_HEAVY, 600 if c == COLORS["white"] else 900, stroke=stroke) for tx, c, sz, _ in toks]
    total = sum(im.width for im in ims) / S
    x = cx - total / 2 if anchor == "c" else (cx if anchor == "l" else cx - total)
    row = None       # 一行里已经出现的几段合成一个外框（相邻的段本来就挨着，不算互相压住）
    for (tx, c, sz, ta), im in zip(toks, ims):
        sc, al = pop(t, ta, 0.2)
        put(canvas, im, x + im.width / S / 2, y, sc, al * alpha)
        if _TRACK["on"] and al * alpha >= 0.6 and sc >= 0.6:
            h = im.height / S
            box = (x, y - h / 2, x + im.width / S, y + h / 2)
            row = box if row is None else (min(row[0], box[0]), min(row[1], box[1]), max(row[2], box[2]), max(row[3], box[3]))
        x += im.width / S
    if row is not None:
        _TEXTS.append(("".join(tx for tx, _, _, ta in toks if ta <= t).strip(), *row,
                       max(sz for _, _, sz, ta in toks if ta <= t)))


def draw_formulas(canvas, t):
    for t_in, t_out, toks, y in _formulas:
        if t_in - 0.01 <= t < t_out:
            draw_token_row(canvas, toks, 960, y, t, fade(t, t_in, t_out, 0.12))


def draw_keywords(canvas, t):
    for k in _keywords:
        if not (k["show"] <= t < k["hide"]):
            continue
        sc, al = pop(t, k["pop"], k.get("pop_dur", 0.22))
        im = text_img(k["text"], k.get("size", 100), col(k.get("color", "white")), FONT_HEAVY, 900,
                      stroke=k.get("stroke", 3))
        if k.get("rotate"):
            im = im.rotate(k["rotate"], expand=True, resample=Image.BICUBIC)
        _note_text(k["text"], im, k["x"], k["y"], sc, al * clamp((k["hide"] - t) / 0.1), size=k.get("size", 100))
        put(canvas, im, k["x"], k["y"], sc, al * clamp((k["hide"] - t) / 0.1))


def draw_arrows(canvas, t):
    for a in _arrows:
        alpha = fade(t, a["show"], a["hide"], 0.2)
        if alpha <= 0:
            continue
        lay = new_layer()
        ld = ImageDraw.Draw(lay)
        p = ease_out((t - a["show"]) / 0.5)
        x0, y0 = a["x0"], a.get("y0", a.get("y"))
        x1e, y1e = a["x1"], a.get("y1", a.get("y"))
        x1, y1 = x0 + (x1e - x0) * p, y0 + (y1e - y0) * p
        n = 40
        for i in range(n):
            pa = (x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n)
            pb = (x0 + (x1 - x0) * (i + 1) / n, y0 + (y1 - y0) * (i + 1) / n)
            c = (255, int(150 - 90 * i / n), int(70 - 40 * i / n), 255)
            ld.line([(pa[0] * S, pa[1] * S), (pb[0] * S, pb[1] * S)], fill=c, width=int((4 + 6 * i / n) * S))
        ang = math.atan2(y1e - y0, x1e - x0)
        ca, sa = math.cos(ang), math.sin(ang)
        head = [(30, 0), (-10, -22), (-10, 22)]
        ld.polygon([((x1 + hx * ca - hy * sa) * S, (y1 + hx * sa + hy * ca) * S) for hx, hy in head],
                   fill=COLORS["orange"])
        if a.get("label"):
            put(lay, text_img(a["label"], 46, (255, 255, 255, 255), FONT_HEAVY, 900, stroke=2),
                a.get("label_x", (x0 + x1e) / 2), a.get("label_y", (y0 + y1e) / 2 - 48))
        composite(canvas, lay, alpha)


@lru_cache(maxsize=128)
def sub_img(text):
    f = font(FONT_SUB, _sub.get("size", 64))
    bbox = f.getbbox(text)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 22 * S, 12 * S
    im = Image.new("RGBA", (w + 2 * pad_x, h + 2 * pad_y), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, im.height], fill=(0, 0, 0, _sub.get("box_alpha", 165)))
    d.text((pad_x - bbox[0], pad_y - bbox[1]), text, font=f, fill=(255, 255, 255, 255))
    return im


def draw_subtitles(canvas, t):
    if _sub.get("enabled", True) is False:
        return
    lead = _sub.get("lead", 0.12)
    for i, (s, e, tx) in enumerate(LINES):
        nxt = LINES[i + 1][0] if i + 1 < NL else T_END
        if s - lead <= t < nxt - lead:
            im = sub_img(tx.replace("，", " ").replace(",", " "))
            sc = min(1.0, 1800 * S / im.width)  # 太长就缩小，保证不出画面
            put(canvas, im, 960, _sub.get("y", 1010), sc, fade(t, s - lead, T_END, 0.06))


# ---------------- 题目图形（作品目录/graphics.py） ----------------
ctx = SimpleNamespace(
    S=S, WIDTH=WIDTH, HEIGHT=HEIGHT, FPS=FPS, BEAT=BEAT, B=BEAT, BEAT0=BEAT0, T0=T0, T_END=T_END,
    LINES=LINES, NL=NL, L=L, E=E, C=C, W=W, beat=beat, tm=tm, COLORS=COLORS, col=col,
    FONT_HEAVY=FONT_HEAVY, FONT_SUB=FONT_SUB,
    clamp=clamp, ease_out=ease_out, ease_in_out=ease_in_out, ease_back=ease_back, lerp=lerp,
    fade=fade, pop=pop, beat_flash=beat_flash, red_then=red_then,
    polar=polar, rotate=rotate, shift=shift, along=along, spread=spread,
    font=font, text_img=text_img, text_width=text_width, put=put, new_layer=new_layer, composite=composite, stage=Stage,
    ImageDraw=ImageDraw, Image=Image, math=math, SB=SB,
)
_gfx = None
if SB.get("graphics"):
    gp = WORK / SB["graphics"]
    if not gp.exists():
        _die(f"storyboard.json 里写了 graphics: {SB['graphics']}，但文件不存在")
    spec = importlib.util.spec_from_file_location("topic_graphics", gp)
    _gfx = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_gfx)
    if hasattr(_gfx, "setup"):
        _gfx.setup(ctx)




def render(t):
    _TEXTS.clear()
    canvas = Image.new("RGBA", (WIDTH * S, HEIGHT * S), (0, 0, 0, 0))
    if _gfx is not None:
        _gfx.draw(canvas, t, ctx)
    if _TRACK["on"]:
        bb = canvas.getchannel("A").getbbox()
        _TRACK["bbox"] = tuple(v / S for v in bb) if bb else None
    draw_arrows(canvas, t)
    draw_keywords(canvas, t)
    draw_formulas(canvas, t)
    draw_banner(canvas, t)
    draw_subtitles(canvas, t)
    out = canvas.resize((WIDTH, HEIGHT), Image.LANCZOS) if S != 1 else canvas
    if t > T_END - 0.4:  # 片尾淡出
        k = clamp((T_END - t) / 0.4)
        out.putalpha(out.getchannel("A").point(lambda v: int(v * k)))
    return out


def line_preview_time(i, at=None):
    """第 i 句的代表时间。默认是这句快唱完时（下一句开始前 0.2 秒），这样句尾才触发的动作也拍得到；
    at=0.5 这样的比例表示取这句到下一句之间的某个位置。"""
    s0 = LINES[i - 1][0]
    nxt = LINES[i][0] if i < NL else T_END
    if at is not None:
        return s0 + clamp(at) * (nxt - s0)
    return max(s0 + 0.05, nxt - 0.2)


BG_PREVIEW = (26, 28, 36, 255)


def preview_frame(t):
    im = Image.new("RGBA", (WIDTH, HEIGHT), BG_PREVIEW)
    im.alpha_composite(render(t))
    return im


def line_at(t):
    return max((i + 1 for i in range(NL) if LINES[i][0] <= t), default=1)


def make_sheet(times, labels, cols, tw, th, out_path):
    rows = (len(times) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
    lf = ImageFont.truetype(FONT_SUB, max(20, tw // 22))
    for n, (t, lab) in enumerate(zip(times, labels)):
        tile = preview_frame(t).resize((tw, th), Image.LANCZOS).convert("RGB")
        ImageDraw.Draw(tile).text((8, 5), lab, fill=(255, 216, 74), font=lf, stroke_width=2, stroke_fill=(0, 0, 0))
        sheet.paste(tile, ((n % cols) * tw, (n // cols) * th))
    sheet.save(out_path, quality=88)
    print(out_path)


if __name__ == "__main__":
    if MODE == "info":
        vals = {x: tm(x, "info") for x in sys.argv[3:]}
        print(json.dumps({"t0": T0, "t_end": T_END, "fps": FPS, "song": SONG, "bpm": BPM, "beat0": BEAT0,
                          "lines": [[s, e, tx] for s, e, tx in LINES], "values": vals, "font_heavy": FONT_HEAVY,
                          "preview_times": [line_preview_time(i) for i in range(1, NL + 1)]}, ensure_ascii=True))
    elif MODE in ("png", "pnga"):
        for x in sys.argv[3:]:
            t = tm(x, MODE)
            (render(t) if MODE == "pnga" else preview_frame(t)).save(WORK / f"预览_{t:.2f}.png")
            print(WORK / f"预览_{t:.2f}.png")
    elif MODE == "sheet":
        rest = sys.argv[3:]
        at = float(rest[rest.index("--at") + 1]) if "--at" in rest else None
        times = [line_preview_time(i, at) for i in range(1, NL + 1)]
        if "--pages" in rest:
            per = 6
            for pg in range(0, NL, per):
                idx = list(range(pg, min(NL, pg + per)))
                make_sheet([times[i] for i in idx], [f"{i + 1}  {times[i]:.1f}s" for i in idx], 2, 960, 540,
                           WORK / f"分镜预览_p{pg // per + 1}.jpg")
        make_sheet(times, [str(i + 1) for i in range(NL)], 4, 480, 270, WORK / "分镜预览.jpg")   # 总览每次都更新
    elif MODE == "frames":
        if len(sys.argv) < 5:
            _die("用法：frames <起> <止> [步长秒，默认 0.25]，例：frames L(18) L(19) 0.2")
        a_, b_ = tm(sys.argv[3], "frames"), tm(sys.argv[4], "frames")
        step = float(sys.argv[5]) if len(sys.argv) > 5 else 0.25
        times, t = [], a_
        while t <= b_ + 1e-6 and len(times) < 36:
            times.append(t)
            t += step
        make_sheet(times, [f"{x:.2f}s 第{line_at(x)}句" for x in times], 3, 640, 360, WORK / "分镜逐帧.jpg")
    elif MODE == "cover":
        # 给 build_video 挑背景用：每个时间点上，题目图形的外框占画面的比例（0 表示这时没有图形）
        _TRACK["on"] = True
        fr = []
        for x in sys.argv[3:]:
            try:
                render(tm(x, "cover"))
                bb = _TRACK["bbox"]
            except Exception:  # noqa: BLE001
                bb = None
            fr.append(round((bb[2] - bb[0]) * (bb[3] - bb[1]) / (WIDTH * HEIGHT), 4) if bb else 0.0)
        print(json.dumps(fr))
    elif MODE == "check":
        problems = []
        if T_END <= T0:
            problems.append(f"t_end({T_END}) 不大于 t0({T0})")
        for n, (a, b, toks, _) in enumerate(_formulas):
            if b <= a:
                problems.append(f"formulas[{n}] 的 hide 不晚于 show")
            for tx, _, _, ta in toks:
                if not (a - 0.05 <= ta <= b):
                    problems.append(f"formulas[{n}]「{tx}」出现时间 {ta:.2f} 不在显示区间 {a:.2f}–{b:.2f} 内")
        for n in range(len(_formulas)):
            for m in range(n + 1, len(_formulas)):
                a1, b1, _, y1_ = _formulas[n]
                a2, b2, _, y2_ = _formulas[m]
                if min(b1, b2) - max(a1, a2) > 0.05 and abs(y1_ - y2_) < 70:
                    problems.append(f"formulas[{n}] 和 formulas[{m}] 同时显示而且在同一行（y={y1_} / {y2_}），会叠在一起。"
                                    f"让前一条先 hide，或者给其中一条写不同的 y")
        for k in _keywords:
            if not (k["show"] <= k["pop"] < k["hide"]):
                problems.append(f"keywords「{k['text']}」需要 show ≤ pop < hide")
        # 试画 + 版面：图形层有没有顶到横幅、压到字幕、和公式行重叠、碰到画面边缘
        _TRACK["on"] = True
        SMALL = "图形偏小（宽不到 520、高不到 320），在手机上会看不清；主图形建议宽 800 以上或高 400 以上"
        EMPTY = "画面中间是空的（没有图形、弹字、公式）"
        MIN_SPAN = {SMALL: 1.2, EMPTY: 1.2}      # 这两类只报持续超过 1.2 秒的
        bad, layout, t = [], {}, T0
        clashes = {}
        tiny = {}

        def _overlap(a, b):
            """两块文字的外框各往里收 12% 后还重叠，而且重叠部分占小的那块 15% 以上，才算压住。"""
            def shrink(r):
                dx, dy = (r[2] - r[0]) * 0.12, (r[3] - r[1]) * 0.12
                return r[0] + dx, r[1] + dy, r[2] - dx, r[3] - dy
            a0, a1, a2, a3 = shrink(a[1:5])
            b0, b1, b2, b3 = shrink(b[1:5])
            w, h = min(a2, b2) - max(a0, b0), min(a3, b3) - max(a1, b1)
            if w <= 0 or h <= 0:
                return False
            small = min((a2 - a0) * (a3 - a1), (b2 - b0) * (b3 - b1))
            return small > 0 and w * h / small >= 0.15
        banner_t = _banner["parts"][0][1] if _banner else None
        banner_bottom = (_banner.get("y", 78) + _banner.get("size", 84) * 0.72) if _banner else 0
        sub_top = _sub.get("y", 1010) - _sub.get("size", 64) * 0.8
        while t < T_END:
            try:
                render(t)
                bb = _TRACK["bbox"]
                boxes = list(_TEXTS)
                for b_ in boxes:
                    if b_[5] < 34 and LINES[0][0] <= t < LINES[-1][1]:
                        tiny.setdefault(b_[0][:16], []).append(t)
                for i_ in range(len(boxes)):
                    for j_ in range(i_ + 1, len(boxes)):
                        a_, b_ = boxes[i_], boxes[j_]
                        same_spot = a_[0] == b_[0] and abs(a_[1] - b_[1]) < 4 and abs(a_[2] - b_[2]) < 4
                        if not same_spot and _overlap(a_, b_):
                            clashes.setdefault(tuple(sorted((a_[0][:14], b_[0][:14]))), []).append(t)
                if bb:
                    x0, y0, x1, y1 = bb
                    if banner_t is not None and t >= banner_t and y0 < banner_bottom:
                        layout.setdefault("图形顶到了顶部口诀横幅", []).append(t)
                    if _sub.get("enabled", True) is not False and y1 > sub_top:
                        layout.setdefault("图形压到了底部字幕", []).append(t)
                    for f_in, f_out, toks, fy in _formulas:
                        if f_in <= t < f_out and any(ta <= t for _, _, _, ta in toks):
                            half = max(sz for _, _, sz, _ in toks) * 0.55
                            if y1 > fy - half and y0 < fy + half:
                                layout.setdefault(f"图形和公式行（y={fy}）重叠", []).append(t)
                    if x0 <= 1 or y0 <= 1 or x1 >= WIDTH - 1 or y1 >= HEIGHT - 1:
                        layout.setdefault("图形碰到画面边缘，可能被裁掉", []).append(t)
                    if (x1 - x0) < 520 and (y1 - y0) < 320 and LINES[0][0] <= t < LINES[-1][1]:
                        layout.setdefault(SMALL, []).append(t)
                elif LINES[0][0] + 0.5 <= t < LINES[-1][1]:
                    kw_on = any(k["show"] <= t < k["hide"] for k in _keywords)
                    fm_on = any(f_in <= t < f_out and any(ta <= t for _, _, _, ta in toks) for f_in, f_out, toks, _ in _formulas)
                    if not kw_on and not fm_on:
                        layout.setdefault(EMPTY, []).append(t)
            except Exception as e:  # noqa: BLE001
                bad.append((round(t, 2), repr(e)))
            t += 0.25
        for p_ in problems:
            print("分镜问题：", p_)
        for issue, ts in list(layout.items()):
            spans, start, prev = [], ts[0], ts[0]
            for x in ts[1:] + [None]:
                if x is None or x - prev > 0.3:
                    if prev - start >= MIN_SPAN.get(issue, 0):
                        spans.append(f"第{line_at(start)}句 {start:.1f}–{prev:.1f}s" if prev > start
                                     else f"第{line_at(start)}句 {start:.1f}s")
                    start = x
                prev = x
            if not spans:
                del layout[issue]
                continue
            print(f"版面提醒：{issue}：" + "；".join(spans[:8]) + ("…" if len(spans) > 8 else ""))
        n_clash = 0
        for (ta_, tb_), ts in sorted(clashes.items(), key=lambda kv: kv[1][0]):
            if len(ts) < 3:          # 不到半秒的擦身而过不算
                continue
            n_clash += 1
            if n_clash <= 12:
                print(f"版面提醒：文字互相压住：「{ta_}」和「{tb_}」：第{line_at(ts[0])}句 {ts[0]:.1f}–{ts[-1]:.1f}s")
        if n_clash > 12:
            print(f"  …还有 {n_clash - 12} 处文字互相压住")
        if n_clash:
            layout["文字互相压住"] = [0]
        small_txt = [(k_, v_) for k_, v_ in sorted(tiny.items(), key=lambda kv: kv[1][0]) if len(v_) >= 6]
        if small_txt:
            layout["文字偏小"] = [0]
            print("版面提醒：文字偏小（字号不到 34，手机上看不清；说明文字建议 ≥ 44）："
                  + "；".join(f"「{k_}」第{line_at(v_[0])}句" for k_, v_ in small_txt[:10])
                  + (f" …共 {len(small_txt)} 处" if len(small_txt) > 10 else ""))
        if layout:
            print("  （版面提醒不一定是错：自己在图形里画的说明文字靠近这些区域也会被提示。"
                  "用 frames <起> <止> 把这段逐帧排开看一眼。）")
        print(f"检查完成：分镜问题 {len(problems)} 个，渲染出错 {len(bad)} 处，版面提醒 {len(layout)} 类", bad[:10])
        sys.exit(1 if (bad or problems) else 0)
    else:
        a = tm(sys.argv[3], "raw") if len(sys.argv) > 3 else T0
        b = tm(sys.argv[4], "raw") if len(sys.argv) > 4 else T_END
        out = sys.stdout.buffer
        for n in range(round((a - T0) * FPS), round((b - T0) * FPS)):
            t = T0 + n / FPS
            out.write(render(t).tobytes())
            if n % 150 == 0:
                print(f"frame {n} t={t:.2f}", file=sys.stderr, flush=True)
