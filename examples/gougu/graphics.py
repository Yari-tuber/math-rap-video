"""样例题目图形：勾股定理（两直边平方加，斜边平方就是它）。

前半段：直角三角形 3、4、? → 两条直边各长出一个正方形（9、16）→ 斜边长出正方形（25）→ 斜边 = 5；
        换成 6、8、10（形状一样，只换数字）；勾三股四弦五。
原理段：边长 a+b 的大框里摆四个一样的直角三角形。第一种摆法中间空出 c²；
        每个三角形整块平移 / 旋转到第二种摆法（不变形），空出 a² 和 b²。框没变、三角没变，空的一样大。

时间全部按唱词算（L / W / B），换一版音频不用改。写新题目时照这个结构：setup 里算时间，draw 里按句分段。
"""
import math

U = 58                       # 前半段一个单位多少像素：3-4-5 三角形
CX, CY = 873, 586            # 直角顶点
A_ = (CX, CY - 4 * U)        # 竖直边顶端
B_ = (CX + 3 * U, CY)        # 水平边右端
N = (0.8, -0.6)              # 斜边朝外的方向
HYP = [A_, B_, (B_[0] + N[0] * 5 * U, B_[1] + N[1] * 5 * U), (A_[0] + N[0] * 5 * U, A_[1] + N[1] * 5 * U)]
SQ_A = (CX, CY, CX + 3 * U, CY + 3 * U)          # 水平边下面的正方形（3×3）
SQ_B = (CX - 4 * U, CY - 4 * U, CX, CY)          # 竖直边左边的正方形（4×4）

U2, A2, B2 = 64, 3, 4        # 原理段：大框边长 (a+b)·U2
S2 = (A2 + B2) * U2
X0, Y0 = 960 - S2 / 2, 470 - S2 / 2
T = {}


def setup(ctx):
    L, W, B = ctx.L, ctx.W, ctx.B
    T.update(
        tri=L(1) + 0.15, l3=W(2, "三"), l4=W(2, "四"), q=W(2, "斜"), ruler=W(3, "尺"), mess=L(4) + 0.2,
        sqa=W(8, "三"), na=W(8, "九"), sqb=W(8, "四"), nb=W(8, "十"), sqc=W(9, "二"), nc=W(9, "五"),
        five=W(10, "五", 2), six=L(11) + 0.1, n100=W(11, "百"), ten=W(12, "十"), gou=W(13, "勾"), gu=W(13, "股"),
        xian=W(13, "弦"), frame=L(17) + 0.1, fly=[L(18) + 0.25 + k * B / 2 for k in range(4)], c2=W(19, "斜"),
        m0=L(20) + 0.05, m1=max(L(20) + 0.9, W(20, "两") - 0.05), ab=W(20, "两"), pulse=L(21), eq=L(22),
    )


# ---------------------------------------------------------------- 前半段
def grid(st, x0, y0, n, size, color, prog=1.0):
    """正方形里的格子：n×n，按 prog 从左上往右下一条条画出来。"""
    k = size / n
    for i in range(1, n):
        p = ctx_clamp(prog * n - i + 1)
        st.line([(x0 + i * k, y0), (x0 + i * k, y0 + size * p)], color, 3)
        st.line([(x0, y0 + i * k), (x0 + size * p, y0 + i * k)], color, 3)


def ctx_clamp(x):
    return max(0.0, min(1.0, x))


def tilted_grid(st, quad, n, color):
    a, b, c, d = quad
    for i in range(1, n):
        f = i / n
        st.line([lerp(a, b, f), lerp(d, c, f)], color, 3)
        st.line([lerp(a, d, f), lerp(b, c, f)], color, 3)


def lerp(p, q, f):
    return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)


def center(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def part1(ctx, st, t):
    fade_c = lambda c, a: ctx.col(c)[:3] + (int(a),)
    # 正方形长出来之前，三角形放大 1.7 倍画在正中；第 8 句缩回原来大小，给正方形让位置
    k = 1.7 - 0.7 * ctx.ease_in_out(ctx_clamp((t - (T["sqa"] - 0.55)) / 0.5))
    pv = (960, 470)
    z = lambda q: (pv[0] + (q[0] - pv[0]) * k, pv[1] + (q[1] - pv[1]) * k)
    C_, A1, B1 = z((CX, CY)), z(A_), z(B_)
    p = ctx.ease_out((t - T["tri"]) / 0.8)
    six = t >= T["six"] and t < T["gou"]
    la, lb, lc = ("6", "8", "10") if six else ("3", "4", "5")
    na, nb, nc = ("36", "64", "100") if six else ("9", "16", "25")
    # 两条直边长出正方形
    if t >= T["sqa"]:
        sc, al = ctx.pop(t, T["sqa"], 0.25)
        x0, y0, x1, y1 = SQ_A
        st.rect(x0, y0, x1, y1, fill=fade_c("primary_dark", 70 * al), outline="primary", width=5)
        if not six:
            grid(st, x0, y0, 3, x1 - x0, fade_c("primary_light", 120), (t - T["sqa"]) / 0.5)
    if t >= T["sqb"]:
        sc, al = ctx.pop(t, T["sqb"], 0.25)
        x0, y0, x1, y1 = SQ_B
        st.rect(x0, y0, x1, y1, fill=fade_c("primary_dark", 70 * al), outline="primary", width=5)
        if not six:
            grid(st, x0, y0, 4, x1 - x0, fade_c("primary_light", 120), (t - T["sqb"]) / 0.5)
    if t >= T["sqc"]:
        sc, al = ctx.pop(t, T["sqc"], 0.3)
        st.poly(HYP, fill=fade_c("result", 60 * al), outline="result", width=5)
        if not six:
            tilted_grid(st, HYP, 5, fade_c("result", 110))
    # 三角形（勾三股四弦五那句：唱到哪条边，哪条边亮）
    hot_a = T["gou"] <= t < T["gou"] + 0.6
    hot_b = T["gu"] <= t < T["gu"] + 0.6
    hot_c = (T["xian"] <= t < T["xian"] + 0.6 or ctx.beat_flash(t, T["five"], T["five"] + 1.2)
             or ctx.beat_flash(t, T["ten"], T["ten"] + 1.2))
    if p < 1:
        st.line([A1, C_, B1, A1], "primary", 9 * k ** 0.5, prog=p)
    else:
        st.line([A1, C_], "result" if hot_b else "primary", 9)
        st.line([C_, B1], "result" if hot_a else "primary", 9)
        st.line([A1, B1], "result" if hot_c else "primary", 11 if hot_c else 9)
        st.right_angle(C_[0], C_[1], 26, -90, "line", 4)
    # 正方形里的面积数字
    for tt, txt, (x, y) in ((T["na"], na, center([(SQ_A[0], SQ_A[1]), (SQ_A[2], SQ_A[3])])),
                            (T["nb"], nb, center([(SQ_B[0], SQ_B[1]), (SQ_B[2], SQ_B[3])])),
                            (T["nc"], nc, center(HYP))):
        t_show = T["n100"] if (six and txt == "100") else tt
        if t >= t_show:
            sc, al = ctx.pop(t, t_show, 0.22)
            st.text(txt, x, y, 64, "result" if txt in ("25", "100") else "text", 900, stroke=3, scale=sc, alpha=al)
    # 边长：写在三角形里面，小一号，互相错开
    fs = 40 * k
    if t >= T["l3"]:
        sc, al = ctx.pop(t, T["l3"] if not six else T["six"], 0.2)
        st.text(la, *z((CX + 1.5 * U, CY - 22)), fs, "text", 900, stroke=3, scale=sc, alpha=al)
    if t >= T["l4"]:
        sc, al = ctx.pop(t, T["l4"] if not six else T["six"], 0.2)
        st.text(lb, *z((CX + 20, CY - 2.6 * U)), fs, "text", 900, stroke=3, scale=sc, alpha=al, anchor="l")
    if t >= T["q"]:
        if t < T["five"]:
            if t < T["sqc"]:
                mx, my = center([A1, B1])
                kk = 1 + 0.12 * math.sin((t - T["q"]) * 9)
                st.text("?", mx + N[0] * 48 * k, my + N[1] * 48 * k, 60 * k, "highlight", 900, stroke=3, scale=kk)
        else:
            t_lab = T["ten"] if six else T["five"]
            if t >= t_lab or not six:
                sc, al = ctx.pop(t, t_lab, 0.22)
                st.text(lc, *z((CX + 1.25 * U, CY - 1.65 * U)), 44, "result", 900, stroke=3, scale=sc, alpha=al)
    # 陷阱：拿尺子量（歪的）、越量越乱
    if T["ruler"] <= t < T["sqa"] and t < ctx.L(5):
        p2 = ctx.ease_out((t - T["ruler"]) / 0.5)
        a, b = z((A_[0] - 14, A_[1] - 8)), z((B_[0] + 22, B_[1] + 10))
        st.line([a, lerp(a, b, p2)], "highlight", 7)
        if t >= T["mess"]:
            for n in range(6):
                tk = T["mess"] + n * 0.28
                if t >= tk:
                    ang = math.radians(-58 + n * 7 - (n % 2) * 13)
                    o = z((A_[0] - 10 + n * 6, A_[1] - 6 + (n % 3) * 9))
                    st.line([o, (o[0] + 300 * k * math.cos(-ang), o[1] + 300 * k * math.sin(-ang))],
                            fade_c("muted", 170), 4)


# ---------------------------------------------------------------- 原理段
def rigid(R, theta, a, b):
    """直角顶点 R、a 边方向角 theta（度）→ 三角形三个顶点。b 边是 a 边转 +90°（屏幕坐标）。"""
    c, s = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    return [R, (R[0] + a * c, R[1] + a * s), (R[0] - b * s, R[1] + b * c)]


def P(x, y):
    return (X0 + x * U2, Y0 + y * U2)


# 每个三角形：(第一种摆法的直角顶点, a 边角度) → (第二种摆法的直角顶点, a 边角度)
S = A2 + B2
MOVES = [
    ((0, 0), 0, (A2, A2), -90),        # 左上 → 右上那块长方形的左下半
    ((S, 0), 90, (S, 0), 90),          # 右上：不动
    ((S, S), 180, (A2, S), 180),       # 右下 → 左下那块长方形的下半（平移）
    ((0, S), -90, (0, A2), 0),         # 左下 → 左下那块长方形的上半（转 90°）
]


def part2(ctx, st, t):
    fade_c = lambda c, a: ctx.col(c)[:3] + (int(a),)
    p = ctx.ease_out((t - T["frame"]) / 0.6)
    st.line([P(0, 0), P(S, 0), P(S, S), P(0, S), P(0, 0)], "line", 7, prog=p)
    m = ctx.ease_in_out(ctx_clamp((t - T["m0"]) / (T["m1"] - T["m0"])))
    # 空出来的地方先画（在三角形下面）
    if T["c2"] <= t < T["m0"] + 0.05:
        sc, al = ctx.pop(t, T["c2"], 0.3)
        quad = [P(A2, 0), P(S, A2), P(S - A2, S), P(0, S - A2)]
        st.poly(quad, fill=fade_c("result", 90 * al), outline="result", width=5)
        st.text("c²", *center(quad), 72, "result", 900, stroke=3, scale=sc, alpha=al)
    if t >= T["ab"]:
        sc, al = ctx.pop(t, T["ab"], 0.3)
        for (x0, y0, x1, y1, lab) in ((0, 0, A2, A2, "a²"), (A2, A2, S, S, "b²")):
            st.rect(*P(x0, y0), *P(x1, y1), fill=fade_c("result", 90 * al), outline="result", width=5)
            st.text(lab, *center([P(x0, y0), P(x1, y1)]), 64, "result", 900, stroke=3, scale=sc, alpha=al)
    hot = ctx.beat_flash(t, T["pulse"], ctx.L(22))
    for k, ((r0, th0, r1, th1)) in enumerate(MOVES):
        if t < T["fly"][k]:
            continue
        sc, al = ctx.pop(t, T["fly"][k], 0.25)
        dth = (th1 - th0 + 180) % 360 - 180
        c0 = center(rigid(P(*r0), th0, A2 * U2, B2 * U2))          # 绕三角形中心转，路线最顺
        c1 = center(rigid(P(*r1), th1, A2 * U2, B2 * U2))
        cm = lerp(c0, c1, m)
        local = rigid((0, 0), th0 + dth * m, A2 * U2, B2 * U2)
        g = center(local)
        pts = [(x - g[0] + cm[0], y - g[1] + cm[1]) for x, y in local]
        if sc < 0.999:
            cx, cy = center(pts)
            pts = [(cx + (x - cx) * sc, cy + (y - cy) * sc) for x, y in pts]
        st.poly(pts, fill=fade_c("primary_dark", 210 * al), outline="primary_light" if hot else "primary", width=5)
    if hot:
        st.line([P(0, 0), P(S, 0), P(S, S), P(0, S), P(0, 0)], "result", 9)


def draw(canvas, t, ctx):
    L = ctx.L
    st = ctx.stage()
    alpha = 1.0
    if L(1) <= t < L(17):
        if t >= L(15):                # 副歌：图形 0.3 秒淡出，让口诀大字唱
            alpha = 1 - ctx.clamp((t - L(15)) / 0.3)
            if alpha <= 0:
                return
        part1(ctx, st, t)
    elif t >= L(17):
        part2(ctx, st, t)
        alpha = ctx.fade(t, L(17), ctx.T_END, 0.25)
    st.commit(canvas, alpha)
