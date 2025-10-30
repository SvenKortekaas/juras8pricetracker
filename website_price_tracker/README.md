# Website Price Tracker (MQTT)

Universele Home Assistant-add-on voor het monitoren van prijzen op willekeurige webshops. De add-on scrapt ingestelde productpagina’s, normaliseert prijzen en publiceert alles automatisch via MQTT Discovery als sensoren (met optionele attributen en historie).

## Configuratievelden
- `product_name` *(optioneel, standaard `Website Price Tracker`)*: Friendly naam die in Home Assistant voor de sensoren en de handmatige refresh-knop verschijnt.
- `run_time` *(optioneel, `HH:MM`)*: Dagelijkse uitvoering op een specifiek tijdstip (krijgt voorrang op `scan_interval`).
- `scan_interval` *(seconden)*: Interval tussen runs zolang `run_time` niet is ingesteld.
- `log_level` *(optioneel, standaard `info`)*: Minimale logniveau (`debug`, `info`, `warning`, `error`).
- `sites`: Lijst met `{ id, url, title?, headers?, price_divisor? }`
  - Gebruik `price_divisor` voor shops die prijzen in centen of met een factor 10 teruggeven.

## Voorbeeld
```yaml
options:
  product_name: "PlayStation 5 Tracker"
  scan_interval: 3600
  base_topic: ps5_prices
  mqtt_host: core-mosquitto
  mqtt_port: 1883
  min_price: 300
  max_price: 800
  sites:
    - id: coolblue
      title: "Coolblue"
      url: "https://www.coolblue.nl/product/123456/playstation-5.html"
    - id: bol
      title: "Bol.com"
      url: "https://www.bol.com/nl/nl/p/playstation-5/9300000000000/"
      headers:
        Cookie: "example=1"
```

Gebruik `log_level: debug` voor uitgebreidere foutanalyse in de add-on logviewer.

## Handmatige refresh
- Via MQTT Discovery verschijnt automatisch een knop `<product_name> Refresh` in Home Assistant.
- Verstuur `PRESS` naar `<base_topic>/command/refresh` of druk op de knop om meteen een nieuwe scrape-cyclus te starten (ongeacht de geplande interval).

