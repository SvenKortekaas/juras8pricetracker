# Jura S8 Price Tracker (MQTT)

Scrapet prijzen voor de **Jura S8 Piano Black EB** bij meerdere NL shops en publiceert via **MQTT Discovery** als sensoren met historie.

## Config-velden
- `run_time` *(optioneel, `HH:MM`)*: eenmaal per dag op dit tijdstip (heeft voorrang op `scan_interval`).
- `scan_interval` *(seconden)*: interval tussen runs als `run_time` niet is ingesteld.
- `log_level` *(optioneel, standaard `info`)*: minimaal logniveau voor de add-on logstream (bijvoorbeeld `debug`, `info`, `warning`).
- `sites`: lijst van `{ id, url, title?, headers?, price_divisor? }`
  - Gebruik `price_divisor` om sites te normaliseren die prijzen in centen of met een factor 10 publiceren.

### Voorbeeld
```yaml
options:
  run_time: "06:00"
  log_level: debug
  base_topic: jura_s8
  mqtt_host: core-mosquitto
  mqtt_port: 1883
  sites:
    - id: coolblue
      url: "https://www.coolblue.nl/product/947474/jura-s8-piano-black-eb.html"
    - id: koffiestore
      url: "https://koffiestore.nl/products/jura-s8-piano-black-eb"
      price_divisor: 10
```

Gebruik `log_level: debug` voor uitgebreide foutopsporing in de add-on logviewer.
