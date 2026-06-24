# 32x8 HUB75 framebuffer. Hardware (rgb/hub75) guarded for host imports.
try:
    import rgb, hub75
except ImportError:
    rgb = hub75 = None

W, H = 32, 8
fb = [0] * (W * H)


def fb_clear():
    for i in range(W * H):
        fb[i] = 0


def px(x, y, color):
    if 0 <= x < W and 0 <= y < H:
        r, g, b = color
        fb[y * W + x] = (r << 24) | (g << 16) | (b << 8) | 255


def fb_blit():
    rgb.clear()
    hub75.image(fb, 0, 0, W, H)
