"""Carousel: keeps showing the same stat by identity across active-list rebuilds."""

from pixelbadge.carousel import Carousel


def test_tracks_identity_across_refresh(app):
    a, b, c = {"id": "A"}, {"id": "B"}, {"id": "C"}
    car = Carousel([a, b, c])
    assert car.current()["id"] == "A"
    car.step(1)
    assert car.current()["id"] == "B"
    # active list reorders (e.g. a battery dropped, solar appeared) — stay on B
    car.refresh([c, b, a])
    assert car.current()["id"] == "B"


def test_falls_back_when_current_drops_out(app):
    car = Carousel([{"id": "A"}, {"id": "B"}, {"id": "C"}])
    car.step(1)  # on B
    car.refresh([{"id": "A"}, {"id": "C"}])  # B went idle
    assert car.current()["id"] == "A"


def test_step_wraps_both_ways(app):
    car = Carousel([{"id": "X"}, {"id": "Y"}])
    car.step(-1)
    assert car.current()["id"] == "Y"
    car.step(1)
    assert car.current()["id"] == "X"
