"""Framebuffer-level characterization: px / draw_text / bar_left.
Targets app.* names so it stays valid before and after extraction."""


def test_px_packs_color(app):
    app.fb_clear()
    app.px(0, 0, (255, 0, 0))
    assert app.fb[0] == (255 << 24) | (0 << 16) | (0 << 8) | 255


def test_px_clips_offscreen(app):
    app.fb_clear()
    for x, y in [(-1, 0), (32, 0), (0, -1), (0, 8)]:
        app.px(x, y, (255, 255, 255))
    assert all(v == 0 for v in app.fb)


def test_bar_left_half_lights_16(app):
    app.fb_clear()
    app.bar_left(7, 0.5, (1, 2, 3))
    row = [app.fb[7 * 32 + i] for i in range(32)]
    assert sum(1 for v in row if v) == 16
    assert row[0] and not row[16]


def test_draw_text_one_lights_glyph_cells(app):
    app.fb_clear()
    app.draw_text(0, 0, "1", (255, 255, 255))
    assert sum(1 for v in app.fb if v) == 8
