from pixelbadge.matrix import W, px


def bar_left(y, frac, color):
    n = int(min(1.0, frac) * W + 0.5)
    for i in range(n):
        px(i, y, color)
