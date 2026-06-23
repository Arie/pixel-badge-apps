# Pixel Badge Apps

MicroPython apps for the CampZone 2019 "Pixel" badge (badge.team firmware).

## ha_energy — Home Assistant energy display
Shows live power flows and home-battery SOC from Home Assistant on the 32×8 LED
matrix. See [docs/2026-06-23-ha-energy-app-design.md](docs/2026-06-23-ha-energy-app-design.md).

- `mockup/` — browser simulator used to design the layout/colors/navigation.
  Open `energy-sim.html` (served via the brainstorm companion, or any static server).
- `app/` — the on-badge MicroPython app (deployed to `apps/ha_energy/`).
- Copy `app/config.example.json` → `app/config.json` and fill in your HA token
  and entity IDs (gitignored).
