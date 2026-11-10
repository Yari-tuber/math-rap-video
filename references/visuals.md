# 画面：版式、storyboard.json、graphics.py

目录：1 版式 · 2 时间写法 · 3 storyboard.json 字段 · 4 graphics.py 和画图工具 · 5 写图形的套路 · 6 常见题型 · 7 预览和排查

## 1. 版式（1920×1080）

| 元素 | 位置 | 样式 | 谁画 |
|---|---|---|---|
| 口诀横幅 | 顶部，占 y≈30–140 | 白色粗黑体 84 + 黑描边，分段弹出后常驻 | 引擎 `banner` |
| **主图形** | **中间 y≈180–760** | 蓝为主，粗线（≥9）、实心大点；正在讲的部分先红后蓝 | `graphics.py` |
| 计数 / 标注 | 图形旁边 | 黄色粗体 ≥44 | `graphics.py` |
| 弹字 | 图形右侧 x≈1640，或居中 | 白 / 红 / 黄粗体 100–190，回弹出现 | 引擎 `keywords` |
| 箭头 | 图形上方 | 橙红渐变 + 标签 | 引擎 `arrows` |
| 公式 | y≈830 居中（占 780–880） | 白色 64–70 逐项弹出，结果黄色 84–92 | 引擎 `formulas` |
| 字幕 | 底部，占 y≈960–1060 | 白字 64 + 半透明黑底，一句一换 | 引擎，自动 |
| 背景 | 全屏 | 素材库片段，自动压暗、降饱和、加暗角 | `build_video.py` |

配色名：`white` `yellow` `red` `blue` `blue_dark` `blue_light` `green` `gray` `orange` `line`（浅色线）。也可以写 `[r,g,b]` 或 `[r,g,b,a]`（a 是 0–255 的不透明度）。

经验：
- 图形要"实"：线宽 ≥ 9，点半径 ≥ 20，字号 ≥ 44。细线在暗背景上显得单薄
- 图形要"大"：观众在手机上看。主图形宽 ≥ 800 或高 ≥ 400，圆和扇形半径 ≥ 260，三角形边长 ≥ 500。一排元素用 `ctx.spread(n)` 铺满 x≈240–1680：6 个方块每个约 190×130，10 个方块每个约 130×110，方块里的字号 ≥ 50。`check` 会提醒持续偏小的图形和中间空着的画面
- 主图形不要进入口诀横幅（y<140）和字幕（y>960）的区域；自己在图形里写的说明文字也一样
- 弹字和说明文字放在图形旁边的空白处，不要压在图形上
- 同一时刻只强调一件事：正在讲的那部分用红色，其余保持蓝色
- 相邻色块之间如果留缝，缝宽 ≥ 8，或者在下面垫一块深色底。几像素的透明细缝在会动的背景上会被压糊
- 数列很长时（1 到 100）只画头三个、省略号、尾三个；要讲原理时换成能画全的小例子（1 到 10）

## 2. 时间写法（最重要）

分镜里所有时间都写成**相对歌词的表达式**（字符串），不要写死秒数：

| 写法 | 含义 |
|---|---|
| `L(6)` / `E(6)` | 第 6 句的起点 / 终点 |
| `W(9,'四')` | 第 9 句里"四"这个字唱出来的时间（这句里有几个"四"时，指第 1 个） |
| `W(9,'四',2)` | 第 9 句里第 2 个"四" |
| `C(9,3)` | 第 9 句第 3 个字的时间 |
| `B` | 一拍的长度；`L(6)+2*B` 是第 6 句开始后 2 拍 |
| `beat(k)` | 全曲第 k 拍的时间 |
| `T0` / `T_END` | 成片的起止（默认：第一句前 0.18 秒到最后一句后 0.35 秒） |
| `NL` | 总句数 |

为什么：画面要卡在唱词上，而每版音频的时间都不一样。写成 `W(10,'十')`，"=10条"就永远在唱到"十"的那一下出现；客户换了音频，重跑 `prepare_audio.py` 就行。

`W()` 里的字必须在那句歌词里原样出现，否则 `check` 会报"第 N 句里找不到…"。可以写一个字，也可以写连着的几个字（`W(10,'五千')` 是"五千"开始唱的时间）。

## 3. storyboard.json

```jsonc
{
  "timing": "timing.json",          // prepare_audio.py 的输出
  "graphics": "graphics.py",        // 本题图形；不需要图形时可以不写

  "banner": {                       // 顶部口诀
    "parts": [["口诀：", "W(5,'口')"], ["点数减一，", "L(6)"], ["连加到一", "W(6,'连')"]],   // [文字, 出现时间]
    "pulses": ["L(15)", "L(23)"],   // 再次唱到口诀时横幅跳一下
    "size": 84, "y": 78             // 可选。口诀超过 12 个字时把 size 调小（如 72）
  },

  "formulas": [                     // 公式逐项弹出；一条公式一个显示区间
    {"show": "L(9)", "hide": "L(12)", "y": 830,          // y 可选，默认 830
     "tokens": [["4", "white", 70, "W(9,'四',2)"], [" + 3", "white", 70, "W(9,'三')"],
                [" = 10条", "yellow", 92, "W(10,'十')"]]}      // [文字, 颜色, 字号, 出现时间]
  ],

  "keywords": [                     // 弹字
    {"text": "=？", "show": "L(2)+0.5", "pop": "L(2)+0.62", "hide": "L(3)",
     "x": 1640, "y": 550, "size": 180,
     "color": "white", "stroke": 3, "rotate": 0, "pop_dur": 0.22}     // 这一行都可选
  ],

  "arrows": [                       // 方向箭头：水平写 x0,x1,y；斜的写 x0,y0,x1,y1
    {"show": "L(7)+0.6", "hide": "W(9,'四',2)", "x0": 470, "x1": 1450, "y": 430, "label": "从左往右"}
  ],

  "backgrounds": {
    "seed": 1,                      // 换个数字 = 换一套随机挑选
    "plan": [["T0", "problem"], ["L(3)", "trap"], ["L(5)", "reveal"], ["L(7)", "transition"],
             ["L(9)", "demo:quiet"], ["L(12)", "demo:quiet"], ["L(15)", "hook"], ["L(17)", "principle:quiet"],
             ["L(19)", "principle:quiet"], ["L(21)", "aha"], ["L(23)", "outro"]]
  },

  "vertical": {"title": "竖屏版上方的大标题", "sub": "下方小字（可选）"}    // make_vertical.py 会自动读；命令行的 --title / --sub 优先
}
```

公式的规则：同一时间只能有一条公式显示在同一行。下一条的 `show` 要不早于上一条的 `hide`；确实要同时显示两条，就给其中一条写不同的 `y`（如 740）。`check` 会报同行重叠的公式。

其他可选字段：`fonts`（`{"heavy": ["路径"], "subtitle": ["路径"]}`）、`colors`（改配色）、`subtitles`（`{"y":1010,"size":64,"enabled":true}`）、`t0` / `t_end`（覆盖成片起止）、`backgrounds.library` / `grade` / `lead`。

背景计划的规则：
- 每项是 `[切入时间, 用途]`。用途有 9 种：`problem` 抛问题、`trap` 陷阱、`reveal` 给口诀、`demo` 示范、`transition` 过渡、`hook` 口诀大字、`principle` 原理、`aha` 恍然大悟、`outro` 收尾
- **安静片段是自动挑的**：`bg` 会看每一段中间有没有题目图形，有就只挑"安静"片段（暗、没有亮的人脸特写），这种用途没有安静片段时从别的用途借。所以一般不用管
- 想手动控制时：用途后加 `:quiet` 强制只挑安静片段（比如这一段只有弹字和说明文字，没有图形）；加 `:any` 表示这一段不限制；`"auto_quiet": false` 关掉自动判断
- 也可以直接写片段名（如 `BG05_Candle`）固定用某一段
- 每 2 句左右换一次（约 5 秒）。一段素材约 8 秒，超过 3 句不换会被放慢
- 切点写在句首（`L(n)`），脚本自动提前 0.1 秒，不会在一句话中间切

## 4. graphics.py 和画图工具

```python
T = {}

def setup(ctx):                     # 可选。渲染前调用一次：把动作时间算好
    T["sum"] = ctx.W(10, "十")

def draw(canvas, t, ctx):           # 每帧调用；t 是音频时间
    st = ctx.stage()                # 一个图层。坐标、半径、线宽都按 1920×1080 写
    if ctx.L(1) <= t < ctx.L(5):
        st.line([(400, 560), (1500, 560)], "line", 9)
        sc, al = ctx.pop(t, ctx.L(1) + 0.5)
        st.dot(960, 560, 22 * sc, "white", "blue_dark", 7)
    st.commit(canvas, alpha=1.0)    # 贴到画面上（alpha 可做整组淡入淡出）
```

### Stage 的画图方法

| 方法 | 作用 |
|---|---|
| `st.line(pts, color, width, curve=False, prog=1.0)` | 线段 / 折线。`prog` 0–1 表示画出前面多少（按长度），用来"描出"一条线 |
| `st.dashed(pts, color, width)` | 虚线（pts 要密，比如 `st.arc_points(...)` 的采样点） |
| `st.dot(x, y, r, fill, outline, width)` | 实心圆点 |
| `st.ring(x, y, r, color, width)` | 圆圈（圈出正在讲的元素） |
| `st.rect(x0, y0, x1, y1, fill, outline, width, radius)` | 矩形 / 圆角矩形 |
| `st.poly(pts, fill, outline, width)` | 多边形（三角形、拼图块、台阶） |
| `st.tile(x, y, w, h, text, fill, text_color, size, scale, alpha)` | 带数字的圆角方块，以 (x,y) 为中心；`scale` 配合 `ctx.pop` 做弹出 |
| `st.arc(xa, xb, y, height, prog, color, width, below, dashed)` | 水平线上两点之间的拱形弧（配对、连线） |
| `st.wedge(cx, cy, r, a0, a1, fill, outline, width)` | **扇形：画一个角**。顶点 (cx,cy)，从 a0 度到 a1 度 |
| `st.angle_arc(cx, cy, r, a0, a1, color, width)` | 角的弧线标记（不填充） |
| `st.right_angle(cx, cy, size, a0, color, width)` | 直角符号：一条边朝 a0 度，另一条朝 a0+90 度 |
| `st.stack(x, y_bottom, w, unit_h, n, fill, outline, width, gap, label)` | 一摞 n 个单位方格（台阶、柱子、数方块）：以 x 为中心从 y_bottom 往上摞；返回柱顶的 y |
| `st.brace(x0, x1, y, label, color, size, below)` | 水平括线 + 说明文字（"10 个数"） |
| `st.brace_v(x, y0, y1, label, color, size, left)` | 竖直括线 + 说明文字 |
| `st.text(s, x, y, size, color, weight, stroke, scale, alpha, anchor, rotate)` | 文字。`anchor`: c 居中 / l 左对齐 / r 右对齐 |
| `st.tokens(toks, x, y, t)` | 一行多段文字，各段有自己的颜色、字号、出现时间，整行居中。`toks=[(文字, 颜色, 字号, 时间), …]` |
| `st.image(im, x, y, scale, alpha)` | 贴一张 PIL 图（`ctx.text_img` 的返回值，或自己打开的图片） |
| `st.commit(canvas, alpha)` | 把这层贴上去 |

**角度约定**：0° 向右，逆时针为正，90° 向上（数学课本的习惯）。

**半透明**：颜色写成 `[r,g,b,a]`（a<255）时，`dot / rect / poly / wedge / tile` 的填充会和下面已经画的东西混合，可以叠色。线条和描边不混合。

### ctx 里的工具

| 名字 | 作用 |
|---|---|
| `L(i)` `E(i)` `W(i,字)` `C(i,k)` `B` `beat(k)` `T0` `T_END` `NL` | 时间 |
| `pop(t, t0, dur)` → `(缩放, 透明度)` | 回弹出现；t0 之前是 (0, 0) |
| `fade(t, 入, 出, d)` | 淡入淡出系数（0–1）：从"入"开始用 d 秒升到 1，到"出"之前 d 秒降回 0；区间外是 0。不写"出"就只淡入 |
| `ease_out(x)` `ease_in_out(x)` | 缓动（x 是 0–1 的进度） |
| `lerp(a, b, p)` | 数或坐标点的插值 |
| `red_then(t, t0, hold, first, then)` | 刚出现时是强调色，hold 秒后变成常规色（"先红后蓝"） |
| `beat_flash(t, 起, 止)` | 每拍开头返回 True，做跟拍闪烁 |
| `polar(cx, cy, r, deg)` | 从一点出发、某个方向、某个距离的点 |
| `rotate(pts, center, deg)` / `shift(pts, dx, dy)` | 把一组点整体旋转 / 平移（整块图形搬动） |
| `along(path, p)` | 沿折线走到比例 p 处的点（让图形沿路线移动） |
| `spread(n, x0=240, x1=1680)` | 把 n 个元素等距排开，返回每个元素的中心 x（一排方块、一排点） |
| `text_width(s, size)` | 文字宽度（自己排版对齐时用） |
| `text_img(s, size, color, ...)`、`S` | 底层接口：文字小图、超采样倍数。一般用不到 |

## 5. 写图形的套路

1. **先在 `setup` 里列时间表**：每个动作一个时间，全部用 `L()` / `W()` 算
2. **`draw` 里按唱词分段**：`if L(1) <= t < L(12): … elif L(12) <= t < L(15): …`，每段画这一段该有的东西
3. **逐步出现的东西用进度控制**：`p = (t - 开始) / 时长`，传给 `prog`，或用 `lerp` / `along` 算位置
4. **卡点三件套**：唱到某个数字时，对应的图形先红后蓝出现（`red_then`）+ 被讲的元素套红圈（`ring`）+ 旁边弹出黄色计数
5. **整块搬动**：把图形写成一组点，用 `rotate` 和 `shift` 算出每一帧的位置再 `poly`。路线用 `along`，中途要绕开横幅和别的图形
6. **段落之间整组淡出淡入**：`st.commit(canvas, ctx.fade(t, 段起, 段止, 0.2))`
7. **写一小段就出图看**（见第 7 节），不要全写完再看

完整例子见 `examples/shuxianduan/graphics.py`（约 130 行）。

## 6. 常见题型怎么画

| 题型 | 主图形 | 关键动作 |
|---|---|---|
| 计数类（线段、角、握手） | `dot` + `arc` | 元素逐个弹出 → 按口诀分组高亮 → 每组旁边计数 |
| 求和类（高斯求和、等差数列） | 一排 `tile`（`ctx.spread` 排开）+ `arc` 配对 + `brace` | 首尾连弧 → 每对的和 → 括线标"几对"（嵌套的弧只在最外层标数字）；原理段用小例子：`st.stack` 搭 1–10 的台阶，后一半翻转盖到前一半上，每列一样高 |
| 角度类（三角形内角和） | `poly` 三角形 + `wedge` 三个彩色角 | 角"撕下来"（`rotate` + `shift`）拼到一条直线上成平角；例题用半圆分成三块显示 180° 被减掉 |
| 拼图类（平方差、圆面积、勾股定理） | `poly` 分块 | 用 `lerp` / `rotate` / `shift` 把块从原位置搬到新位置 |
| 堆叠类（数正方体） | `poly` 画等距小方块 | 一层层变红标数 → 拆成一根根柱子 |
| 应用题（鸡兔同笼、植树问题） | 一排 `tile` 或 `dot` 代替物体 | 假设全是一种 → 一部分变色 → 差值除以每个的差 |

## 7. 预览和排查

```bash
python $SKILL/scripts/overlay_engine.py <目录> png "L(9)+1.5"              # 单帧（深色底）→ 预览_<秒>.png
python $SKILL/scripts/overlay_engine.py <目录> sheet                        # 每句一格的总览
python $SKILL/scripts/overlay_engine.py <目录> sheet --at 0.5               # 改成取每句中间
python $SKILL/scripts/overlay_engine.py <目录> sheet --pages                # 总览 + 大图分页（每格 960×540）
python $SKILL/scripts/overlay_engine.py <目录> frames "L(18)" "L(19)" 0.2   # 一段动画逐帧排开
python $SKILL/scripts/overlay_engine.py <目录> info "W(9,'四',2)" "L(12)"   # 查某个时间表达式是几秒
python $SKILL/scripts/overlay_engine.py <目录> check                        # 时间写法、试画、版面提醒
```

- 总览图每格只有 480×270，只能看"有没有、对不对"；文字压边要看 `--pages` 的大图
- 总览默认取每句快唱完的时刻。句中才出现又消失的东西，用 `--at 0.5` 或 `frames` 看
- `check` 的"版面提醒"会报：图形顶到口诀横幅、压到字幕、和公式行重叠、碰到画面边缘、图形持续偏小、画面中间空着，并给出是第几句、第几秒。"文字互相压住"会报出是哪两块文字（`st.text`、`st.tokens`、弹字、公式之间）。它查不出文字压在线条或色块上，这要看 `--pages` 的大图。它按图形层的外框判断，自己画的说明文字靠得近也会报，所以要用 `frames` 看一眼再决定改不改
- 预览图是深色底，看不到背景。背景上的效果在出片后的 `成片_总览.jpg` 里看
