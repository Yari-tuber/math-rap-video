"""本题专用图形（空白模板）。完整例子见 skill 的 examples/shuxianduan/graphics.py。

setup(ctx)            渲染前调用一次：把每个动作的时间算好，放进 T
draw(canvas, t, ctx)  每帧调用；t 是音频时间（秒）

时间一律用 ctx.L(i)（第 i 句起点）、ctx.W(i, "字")（第 i 句里这个字唱出来的时间）、ctx.B（一拍）来算，
不要写死秒数。画图用 st = ctx.stage()，坐标按 1920×1080 写；主图形放在 y≈180–760 之间，要画得够大（宽 ≥ 800 或高 ≥ 400）。
"""
T = {}


def setup(ctx):
    L, W, B = ctx.L, ctx.W, ctx.B
    T["items_pop"] = [L(1) + 0.6 + k * B / 2 for k in range(5)]   # 例：第 1 句里 5 个元素每半拍弹出一个


def draw(canvas, t, ctx):
    L = ctx.L
    st = ctx.stage()
    alpha = 1.0

    if L(1) <= t < L(5):
        # ---- 第 1–4 句：摆出题目 ----
        for i, tp in enumerate(T["items_pop"]):
            sc, al = ctx.pop(t, tp)
            if sc > 0:
                st.dot(560 + i * 200, 520, 26 * sc, "blue", "white", 5)
        alpha = ctx.fade(t, L(1), L(5), 0.2)

    # elif L(5) <= t < L(9):   # ---- 下一段 ----
    #     ...

    st.commit(canvas, alpha)
