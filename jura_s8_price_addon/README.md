# Jura S8 Price Tracker (MQTT)

Scrapet prijzen voor de **Jura S8 Piano Black EB** bij meerdere NL shops en publiceert via **MQTT Discovery** als sensoren met historie.

## Config-velden
- `run_time` *(optioneel, `HH:MM`)*: eenmaal per dag op dit tijdstip (heeft voorrang op `scan_interval`).
- `scan_interval` *(seconden)*: interval tussen runs als `run_time` niet is ingesteld.
- `log_level` *(optioneel, standaard `info`)*: minimaal logniveau voor de add-on logstream (bijvoorbeeld `debug`, `info`, `warning`).
- `logbook` *(optioneel)*: instellingen voor het wegschrijven naar de Home Assistant logbook service.
  - `enabled`: zet op `true` om Home Assistant logbook entries te ontvangen.
  - `level`: minimaal logniveau dat naar het logbook gestuurd wordt (standaard `warning`).
  - `name`: weergegeven naam van de logboekregel (standaard `Jura S8 Price Tracker`).
  - `entity_id`: optionele entity om aan de logboekregel te koppelen.
  - `include_level`: voeg `[LEVEL]` prefix toe aan logboekberichten (standaard `true`).
- `sites`: lijst van `{ id, url, title?, headers?, price_divisor? }`
  - Gebruik `price_divisor` om sites te normaliseren die prijzen in centen of met een factor 10 publiceren.

### Voorbeeld
```yaml
options:
  run_time: "06:00"
  log_level: debug
  logbook:
    enabled: true
    level: info
    name: "Jura S8 Price Tracker"
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

## Logboek-integratie

De add-on logt gestructureerd naar de Supervisor-add-on logviewer en kan optioneel ook gebeurtenissen naar de Home Assistant logbook service sturen. Hiervoor is het volgende nodig:

- `homeassistant_api` staat op `true` (standaard in `config.yaml`).
- De add-on configuratie heeft `logbook.enabled: true`.

Gebruik `log_level: debug` voor uitgebreide foutopsporing in de add-on logviewer zonder het logboek te overspoelen. Met `logbook.level` bepaal je welke meldingen daadwerkelijk in het Home Assistant logboek verschijnen.
