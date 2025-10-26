# Jura S8 Price Tracker 🏷️

Automatische prijs-tracker voor de **Jura S8 Piano Black EB** koffiemachine.
Ontworpen als **Home Assistant Add-on**, publiceert prijzen van meerdere webshops via **MQTT Discovery** zodat je ze als sensoren kunt volgen, vergelijken en visualiseren.

## 🚀 Functies

- 🕓 Dagelijkse scraping (`run_time`) of interval (`scan_interval`)
- 🛒 Ondersteuning voor o.a. Coolblue, MediaMarkt, De Koffie Winkel, Vos Koffie, Koffie Loods, Koffiestore, Like2Cook, Ludiqx
- 💬 MQTT-sensoren met Home Assistant Discovery
- 📈 Historiek + ApexCharts visualisatie
- 🔁 Automatische GitHub Actions release-flow (semver, changelog, manifest bump)

## 🧩 Installatie

1. Voeg deze repository toe aan Home Assistant: `https://github.com/svenkortekaas/jiras8pricetracker`
2. Installeer **Jura S8 Price Tracker (MQTT)**.
3. Configureer MQTT en `run_time` of `scan_interval`.
4. Start de add-on — sensoren verschijnen automatisch.

## ⚙️ Configuratievoorbeeld

```yaml
options:
  run_time: "06:00"          # draait dagelijks om 06:00
  base_topic: jura_s8
  mqtt_host: core-mosquitto
  mqtt_port: 1883
  sites:
    - id: coolblue
      url: "https://www.coolblue.nl/product/947474/jura-s8-piano-black-eb.html"
```

> `run_time` heeft voorrang op `scan_interval`.

## 📊 Dashboard-snippets

### Template-sensor: laagste prijs
```yaml
template:
  - sensor:
      - name: "Jura S8 – Beste prijs"
        unit_of_measurement: "€"
        state: >
          {% set prices = [
            states('sensor.jura_s8_coolblue')|float(999999),
            states('sensor.jura_s8_mediamarkt')|float(999999),
            states('sensor.jura_s8_dekoffiewinkel')|float(999999)
          ] %}
          {{ (prices|min) if prices|min < 999999 else 'unknown' }}
```

### ApexCharts-card (HACS)
```yaml
type: custom:apexcharts-card
header:
  title: Jura S8 – Prijsverloop (30 dagen)
graph_span: 30d
series:
  - entity: sensor.jura_s8_coolblue
  - entity: sensor.jura_s8_mediamarkt
  - entity: sensor.jura_s8_dekoffiewinkel
yaxis:
  - decimals: 0
```

## ⚡ Ontwikkeling

```
jiras8pricetracker/
├─ repository.json
├─ CHANGELOG.md
├─ LICENSE
├─ jura_s8_price_addon/
└─ .github/workflows/release.yml
```

### Releases
- Gebruik `#major`, `#minor`, of niets (patch) in je commitbericht.
- Voorbeelden:
  - `feat: nieuwe site toegevoegd #minor`
  - `fix: verbeterde parser`
  - `refactor!: breaking changes #major`

## 🪪 Licentie
Vrijgegeven onder de [MIT License](LICENSE).
