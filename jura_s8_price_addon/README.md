# Jura S8 Price Tracker (MQTT)

Scrapet prijzen voor de **Jura S8 Piano Black EB** bij meerdere NL shops en publiceert via **MQTT Discovery** als sensoren met historie.

## Config-velden
- `run_time` *(optioneel, `HH:MM`)*: 1× per dag op dit tijdstip (heeft voorrang op `scan_interval`).
- `scan_interval` *(seconden)*: interval tussen runs als `run_time` niet is ingesteld.
- `sites`: lijst van `{ id, url, title?, headers? }`

### Voorbeeld
```yaml
options:
  run_time: "06:00"
  base_topic: jura_s8
  mqtt_host: core-mosquitto
  mqtt_port: 1883
  sites:
    - id: coolblue
      url: "https://www.coolblue.nl/product/947474/jura-s8-piano-black-eb.html"
```
