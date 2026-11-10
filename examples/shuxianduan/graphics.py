"""样例题目图形：数线段（一条直线上 n 个点，线段数 = (n-1)+…+1）。

引擎约定：
    setup(ctx)               可选，渲染前调用一次：把每个动作的时间算好
    draw(canvas, t, ctx)     每帧调用；t 是音频时间（秒）

写新题目时照这个结构：
  1. setup 里用 ctx.L(i)（第 i 句起点）、ctx.W(i,"字")（第 i 句里某个字唱出来的时间）算时间，
     不要写死秒数，这样换一条音频也不用改。
  2. draw 里按唱词分段：if L(1) <= t < L(12): …
  3. 用 st = ctx.stage() 画：坐标按 1920×1080 写，st.commit(canvas, 透明度) 贴上去。
"""
import math

LINE_Y = 560          # 直线所在高度
T = {}                # 时间表，setup 里填


def setup(ctx):
    L, W, B = ctx.L, ctx.W, ctx.B
    T["five_pop"] = [L(1) + 0.75 + k * B / 2 for k in range(5)]          # 5 个点每半拍弹出一个
    T["messy"] = [(0, 2), (1, 4), (0, 1), (2, 3), (1, 3), (3, 4), (0, 4), (2, 4), (0, 3), (1, 2)]
    # 第 9 句"四三二一"：唱到哪个数字，哪个点就连出一组弧
    T["g5"] = {0: W(9, "四", 2), 1: W(9, "三"), 2: W(9, "二"), 3: W(9, "一")}
    # 第 13 句：六个点，每半拍一组
    T["g6"] = {i: L(13) + 0.3 + i * B / 2 for i in range(5)}
    # 原理段：逐条画弧 (起点, 终点, 时间)
    p = [(0, j, W(18, "连") + k * B / 2) for k, j in enumerate([1, 2, 3, 4])]
    p += [(1, j, W(19, "三") + k * B / 2) for k, j in enumerate([2, 3, 4])]
    p += [(2, j, W(21, "两") + k * B / 2) for k, j in enumerate([3, 4])]
    p += [(3, 4, W(21, "一"))]
    T["p_arcs"] = p
    T["dup"] = W(20, "那")                 # "往前那一条"：A–B 那条闪烁，下方画灰色虚线
    # 原理段每个点被红圈圈住的时间段
    T["rings"] = [(L(18), L(19)), (L(19), L(21)), (L(21), W(21, "第", 2)), (W(21, "第", 2), L(22)), (L(22), L(23))]
    # 点下方的黄色计数：(点序号, 数字, 出现, 消失, 点数)
    g5, g6 = T["g5"], T["g6"]
    badges = [(i, str(4 - i), g5[i], L(12), 5) for i in range(4)]
    badges += [(i, str(5 - i), g6[i], L(15), 6) for i in range(5)]
    badges += [(0, "4", W(18, "四"), ctx.T_END, 5), (1, "3", W(19, "三"), ctx.T_END, 5),
               (2, "2", W(21, "两"), ctx.T_END, 5), (3, "1", W(21, "一"), ctx.T_END, 5),
               (4, "0", W(22, "没"), ctx.T_END, 5)]
    T["badges"] = badges


def point_xs(n):
    span = 920 if n == 5 else 1050
    return [960 - span / 2 + i * span / (n - 1) for i in range(n)]


def arc_h(xa, xb, hscale=1.0):
    """弧的高度：跨得越远越高，这样多条弧不会叠在一起。"""
    return (46 + 60 * abs(xb - xa) / 230) * hscale


def base_line(st, xs, prog=1.0):
    xa = xs[0] - 70
    st.line([(xa, LINE_Y), (xa + (xs[-1] - xs[0] + 140) * prog, LINE_Y)], "line", 9)


def points(ctx, st, xs, labels, t, t_pop=None, ring=None):
    base_line(st, xs)
    for i, x in enumerate(xs):
        sc, al = ctx.pop(t, t_pop[i], 0.18) if t_pop else (1, 1)
        if sc <= 0:
            continue
        if ring == i:
            st.ring(x, LINE_Y, 38, "red", 8)
        st.dot(x, LINE_Y, 22 * sc, "white", "blue_dark", 7)
    for i, x in enumerate(xs):
        sc, al = ctx.pop(t, t_pop[i], 0.2) if t_pop else (1, 1)
        st.text(labels[i], x, LINE_Y + 62, 54, "white", 800, stroke=2, scale=sc, alpha=al)


def draw(canvas, t, ctx):
    L = ctx.L
    red_then_blue = lambda ta, hold=0.45: ctx.red_then(t, ta, hold)   # 刚画出来是红的，随后变蓝
    st = ctx.stage()
    alpha = 1.0
    xs5, xs6 = point_xs(5), point_xs(6)
    g5, g6 = T["g5"], T["g6"]

    if L(1) <= t < L(12):
        # ---- 第一段：画线 → 5 个点弹出 → 乱连（陷阱）→ 按口诀分组连 ----
        if t < L(1) + 0.6:
            base_line(st, xs5, ctx.ease_out((t - L(1)) / 0.6))
            for i, x in enumerate(xs5):
                sc, al = ctx.pop(t, T["five_pop"][i], 0.2)
                st.text("ABCDE"[i], x, LINE_Y + 62, 54, "white", 800, stroke=2, scale=sc, alpha=al)
        else:
            if L(3) <= t < L(5):
                for k, (i, j) in enumerate(T["messy"]):
                    ts = L(3) + 0.25 + k * 0.42
                    c = (255, 255, 255, 190) if (t < L(4) + 0.9 or k % 2 == 0) else "red"
                    st.arc(xs5[i], xs5[j], LINE_Y, arc_h(xs5[i], xs5[j], 1.0 + 0.18 * math.sin(k * 2.1)),
                           (t - ts) / 0.3, c, 6)
            if t >= g5[0] - 0.01:
                for i, tg in g5.items():
                    for k, j in enumerate(range(i + 1, 5)):
                        ta = tg + k * 0.05
                        c = "blue_light" if ctx.beat_flash(t, L(11), L(12)) else red_then_blue(ta)
                        st.arc(xs5[i], xs5[j], LINE_Y, arc_h(xs5[i], xs5[j]), (t - ta) / 0.25, c, 11)
            ring = next((i for i, tg in g5.items() if tg <= t < tg + 0.33), None)
            points(ctx, st, xs5, "ABCDE", t, T["five_pop"], ring)

    elif L(12) <= t < L(15):
        # ---- 换成 6 个点 ----
        m = ctx.ease_out((t - L(12)) / 0.5)
        xs = [a + (b - a) * m for a, b in zip(xs5 + [xs5[-1]], xs6)]
        t_pop = [0, 0, 0, 0, 0, L(12) + 0.35]
        for i, tg in g6.items():
            for k, j in enumerate(range(i + 1, 6)):
                ta = tg + k * 0.04
                st.arc(xs[i], xs[j], LINE_Y, arc_h(xs[i], xs[j]), (t - ta) / 0.25, red_then_blue(ta), 9)
        ring = next((i for i, tg in g6.items() if tg <= t < tg + 0.3), None)
        points(ctx, st, xs, "ABCDEF", t, t_pop, ring)
        alpha = ctx.fade(t, L(12), L(15), 0.2)

    elif L(17) <= t < ctx.T_END:
        # ---- 原理段：每个点只往后连 ----
        dup = T["dup"]
        for (i, j, ta) in T["p_arcs"]:
            c = red_then_blue(ta, 0.5)
            if (i, j) == (0, 1) and dup <= t < dup + 1.25:
                c = "red" if int((t - dup) / 0.2) % 2 == 0 else "blue"
            if ctx.beat_flash(t, L(ctx.NL)):
                c = "blue_light"
            st.arc(xs5[i], xs5[j], LINE_Y, arc_h(xs5[i], xs5[j]), (t - ta) / 0.28, c, 11)
        if t >= dup:
            st.arc(xs5[0], xs5[1], LINE_Y, arc_h(xs5[0], xs5[1], 0.55), (t - dup) / 0.4, "gray", 7,
                   below=True, dashed=True)
        ring = next((i for i, (a, b) in enumerate(T["rings"]) if a <= t < b), None)
        points(ctx, st, xs5, "ABCDE", t, None, ring)
        if dup <= t < L(21):
            sc, al = ctx.pop(t, dup + 0.15, 0.2)
            st.text("算过了", xs5[0] - 150, LINE_Y + 40, 44, (190, 190, 200), 800, stroke=2, scale=sc,
                    alpha=al * ctx.fade(t, dup + 0.15, L(21)))
        alpha = ctx.fade(t, L(17), ctx.T_END, 0.25)

    for (i, txt, ta, tb, n) in T["badges"]:
        if ta <= t < tb:
            if n == 6 and t < L(12) + 0.5:
                continue
            xs = xs5 if n == 5 else xs6
            sc, al = ctx.pop(t, ta, 0.2)
            st.text(txt, xs[i], LINE_Y + 138, 64, "gray" if txt == "0" else "yellow", 900, stroke=3, scale=sc,
                    alpha=al * ctx.fade(t, ta, tb, 0.15))

    st.commit(canvas, alpha)
