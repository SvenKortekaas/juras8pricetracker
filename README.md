# Website Price Tracker (MQTT)

General-purpose Home Assistant add-on that scrapes prices from any set of product pages and publishes the results via MQTT Discovery. Use it to monitor availability, compare price histories, or trigger automations across all your favourite shops.

## Features
- Scheduled scraping via fixed `run_time` or repeating `scan_interval`.
- Optional `product_name` to brand sensors and the manual refresh button per device.
- MQTT Discovery payloads for sensors (state + attributes) with historical data support.
- Smart price normalisation, including heuristics for retailers that report values in cents.
- Manual refresh button exposed over MQTT for on-demand updates.

## Quick Start
1. Add this repository to Home Assistant: `https://github.com/svenkortekaas/mqtt-website-price-tracker`.
2. Install **Website Price Tracker (MQTT)** from the add-on store.
3. Configure MQTT credentials, `product_name`, and the target sites in the add-on options.
4. Start the add-on – Home Assistant will discover sensors and the refresh button automatically.

## Example Configuration
```yaml
options:
  product_name: "Nintendo Switch OLED"
  scan_interval: 2700        # every 45 minutes
  base_topic: switch_prices
  mqtt_host: core-mosquitto
  mqtt_port: 1883
  min_price: 200
  max_price: 450
  sites:
    - id: coolblue
      title: "Coolblue"
      url: "https://www.coolblue.nl/product/123456/nintendo-switch-oled.html"
    - id: mediamarkt
      title: "MediaMarkt"
      url: "https://www.mediamarkt.nl/product/p/nintendo-switch-oled-987654"
```

## Manual Refresh
A retained discovery message registers a button entity named `<product_name> Refresh`. Press it (or publish `PRESS` to `<base_topic>/command/refresh`) to force an immediate scrape, regardless of the configured schedule.

## Repository Layout
```
.
├─ README.md
├─ CHANGELOG.md
├─ repository.yaml
├─ website_price_tracker/   # Home Assistant add-on code
└─ scripts/
   └─ update_changelog.py
```

## License
Released under the [MIT License](LICENSE).
