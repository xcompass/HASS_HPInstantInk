# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant (HASS) integration for tracking HP Instant Ink plan usage. It consists of two main parts:

1. **Custom Component** (`custom_components/hp_instant_ink_local/`) — A Python-based HA platform sensor that polls the HP printer's local XML endpoint to retrieve page counts and ink levels.
2. **Package YAML** (`packages/hp_envy_5540_instant_ink.yaml`) — A single HA package file containing all `input_number`, `input_datetime`, `input_select`, `sensor` (template), and `automation` entities needed to calculate plan usage, rollover pages, overprint costs, and alerts.

## Architecture

### Data Flow

```
HP Printer XML endpoint
  → custom_components/hp_instant_ink_local/sensor.py (HPPrinterData)
  → HA sensors: sensor.hp_printer_subscription_pages, sensor.hp_printer_total_pages,
                sensor.hp_printer_colour_remaining, sensor.hp_printer_black_remaining
  → packages/hp_envy_5540_instant_ink.yaml (template sensors)
  → Lovelace cards (cards/)
```

### Custom Component (`custom_components/hp_instant_ink_local/`)

- `sensor.py` — Fetches `ProductUsageDyn.xml` from the printer every 5 minutes (`MIN_TIME_BETWEEN_UPDATES`). Parses four values via `xmltodict`: subscription impressions (`sp`), total impressions (`tp`), colour ink % (`cr`), black ink % (`br`). The XML path uses `pudyn:` and `dd:` namespaced tags. The printer URL is hardcoded at line 40: `_RESOURCE = 'http://hp-envy.lan/DevMgmt/ProductUsageDyn.xml'`.
- `manifest.json` — Declares domain `hp_instant_ink_local`, version `0.1.0`, no pip requirements (uses `xmltodict` which must be available in HA).
- `__init__.py` — Empty file (required by HA for custom component discovery).

### Package YAML (`packages/hp_envy_5540_instant_ink.yaml`)

Contains all HA configuration entities in a single file:

- **`input_number`** — User-configurable plan parameters (monthly allowance, rollover max, overprint block size/cost, helper inputs for persistence across reboots).
- **`input_datetime`** — Period start date, used to calculate next renewal date.
- **`input_select`** — `Free` vs `Paid` plan type (affects rollover calculation logic).
- **`sensor` (template)** — Derived sensors: pages remaining, rollover remaining, overprint count/cost, days remaining. Key sensor `hp_envy_5540_total_pages_printed` falls back to `input_number.hp_envy_5540_total_pages_printed_inp` when the printer is offline.
- **`automation`** — Three automations: monthly reset (runs at 00:00:05 on the plan anniversary day), low-pages notification (mobile push), and printer state change handler (persists ink/page values to input helpers).

### Lovelace Cards (`cards/`)

- `lovelace_configuration_card.yaml` — Grid card for editing plan parameters (input helpers).
- `lovelace_status_card.yaml` — Grid card showing computed status sensors + ink level gauges.

## Deployment

This repo contains files to be copied into a running Home Assistant instance — there is no build, test, or lint pipeline. Changes are deployed by placing files in the HA config directory:

- `custom_components/hp_instant_ink_local/` → `<HA config>/custom_components/hp_instant_ink_local/`
- `packages/hp_envy_5540_instant_ink.yaml` → `<HA config>/packages/hp_envy_5540_instant_ink.yaml`

The HA `configuration.yaml` must include:
```yaml
default_config:
homeassistant:
  packages: !include_dir_named packages
```

Sensors are registered via `configuration.yaml` (or `sensors.yaml`):
```yaml
- platform: hp_instant_ink_local
  resources:
    - sp
    - tp
    - cr
    - br
```

## Printer-Specific Customisation

When adapting for a different HP printer model, two things may need changing:

1. **URL** in `sensor.py` line 40 — replace `http://hp-envy.lan/DevMgmt/ProductUsageDyn.xml`.
2. **XML tag paths** in `sensor.py` `HPPrinterData.update()` — the `pudyn:` namespace paths for subscription pages, total pages, and ink levels may differ. The colour consumable is identified by `dd:MarkerColor == "CyanMagentaYellow"` and black by `dd:MarkerColor == "Black"`.

## Known Limitations / Notes

- The renewal date template (`hp_envy_5540_next_renewal_date`) does not handle plan start dates on the 29th, 30th, or 31st of the month.
- The `hp_envy_5540_allowance_days_remaining` template depends on `sensor.date` being available (part of `default_config`).
- Overprint cost uses GBP (`£`) — change `unit_of_measurement` in the package YAML if needed.
- The low-pages notification targets `notify.mobile_app_nexus_10` — update this service name to match the actual device.
