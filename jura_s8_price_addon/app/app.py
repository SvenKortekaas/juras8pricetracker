from __future__ import annotations
import os, json, re, asyncio, signal
from dataclasses import dataclass
from typing import Any
from datetime import datetime, time as dtime, timedelta
import httpx
from bs4 import BeautifulSoup
import paho.mqtt.client as mqtt

PRICE_RE = re.compile(r"(?<!\d)(?:€\s*|\bEUR\s*)(\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{2})?)", re.IGNORECASE)
META_HINTS = [
    ('meta[property="product:price:amount"]', "content"),
    ('meta[name="twitter:data1"]', "content"),
    ('meta[itemprop="price"]', "content"),
    ('span[itemprop="price"]', None),
    ('div[data-price]', "data-price"),
    ('span[data-price]', "data-price"),
    ('div[class*="price"]', None),
    ('span[class*="price"]', None),
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0 Safari/537.36"
)

@dataclass
class Site:
    id: str
    url: str
    title: str | None
    headers: dict[str, str]

class App:
    def __init__(self, options: dict[str, Any]):
        self.scan_interval = int(options.get("scan_interval", 1800))
        self.run_time_str = options.get("run_time")
        self.run_time: dtime | None = None
        if self.run_time_str:
            try:
                h, m = map(int, self.run_time_str.split(":"))
                self.run_time = dtime(h, m)
            except Exception:
                print(f"[addon] Ongeldige tijd in run_time: {self.run_time_str} - gebruik HH:MM")

        self.base_topic = options.get("base_topic", "jura_s8").strip().strip("/")
        self.mqtt_host = options.get("mqtt_host", "core-mosquitto")
        self.mqtt_port = int(options.get("mqtt_port", 1883))
        self.mqtt_username = options.get("mqtt_username") or None
        self.mqtt_password = options.get("mqtt_password") or None
        self.min_price = try_float(options.get("min_price")) or 0.0
        self.max_price = try_float(options.get("max_price")) or 1e9
        self.sites = [Site(s["id"], s["url"], s.get("title"), s.get("headers", {}))
                      for s in options.get("sites", [])]

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{self.base_topic}_addon")
        if self.mqtt_username:
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password or "")
        self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)

        self.device = {
            "identifiers": [f"{self.base_topic}_addon"],
            "name": "Jura S8 Price Tracker",
            "manufacturer": "Custom",
            "model": "Home Assistant Add-on",
        }

    def publish_discovery(self, site: Site):
        obj_id = f"{self.base_topic}_{site.id}".lower()
        disc_topic = f"homeassistant/sensor/{self.base_topic}/{site.id}/config"
        state_topic = f"{self.base_topic}/state/{site.id}"
        attr_topic  = f"{self.base_topic}/attr/{site.id}"
        payload = {
            "name": f"Jura S8 – {site.title or site.id}",
            "unique_id": obj_id,
            "state_topic": state_topic,
            "json_attributes_topic": attr_topic,
            "device_class": "monetary",
            "state_class": "measurement",
            "unit_of_measurement": "€",
            "value_template": "{{ value_json.price }}",
            "device": self.device,
        }
        self.client.publish(disc_topic, json.dumps(payload), retain=True, qos=1)

    async def scrape_once(self):
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8"},
            follow_redirects=True,
            timeout=25,
        ) as client:
            for site in self.sites:
                try:
                    self.publish_discovery(site)
                    resp = await client.get(site.url, headers={**client.headers, **(site.headers or {})})
                    try_alt = resp.status_code in (403, 406)
                    resp.raise_for_status()
                    html = resp.text
                    status = resp.status_code
                    method_hint = "ok"
                except httpx.HTTPStatusError as e:
                    if try_alt:
                        alt_headers = {
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Sec-Fetch-Mode": "navigate",
                        }
                        r2 = await client.get(site.url, headers={**alt_headers, **(site.headers or {})})
                        html = r2.text
                        status = r2.status_code
                        method_hint = "retry"
                    else:
                        self.publish_error(site, f"HTTP {e.response.status_code}")
                        continue
                except Exception as ex:
                    self.publish_error(site, f"{type(ex).__name__}: {ex}")
                    continue

                price, currency, method = extract_price(html)
                title = derive_title(html) or site.title or site.id
                # plausibiliteit / correctie
                if price is not None:
                    if not (self.min_price <= price <= self.max_price):
                        # Heuristiek: soms factor 100 of 10 te groot; probeer te repareren
                        fixed = None
                        if price / 100.0 >= self.min_price and price / 100.0 <= self.max_price:
                            fixed = price / 100.0
                            method += "+heuristic_div100"
                        elif price / 10.0 >= self.min_price and price / 10.0 <= self.max_price:
                            fixed = price / 10.0
                            method += "+heuristic_div10"

                        if fixed is not None:
                            price = fixed
                        else:
                            self.publish_error(site, "price_out_of_range", extra={
                                "title": title, "raw_price": price, "min": self.min_price, "max": self.max_price, "method": method
                            })
                            continue
                            
                state_topic = f"{self.base_topic}/state/{site.id}"
                attr_topic  = f"{self.base_topic}/attr/{site.id}"

                self.client.publish(state_topic, json.dumps({"price": price}), retain=False, qos=0)
                self.client.publish(attr_topic, json.dumps({
                    "title": title,
                    "url": site.url,
                    "currency": currency or "EUR",
                    "source_method": method + "+" + method_hint,
                    "status_code": status
                }), retain=False, qos=0)

    def publish_error(self, site: Site, msg: str, extra: dict[str, Any] | None = None):
        attr_topic  = f"{self.base_topic}/attr/{site.id}"
        state_topic = f"{self.base_topic}/state/{site.id}"
        self.client.publish(state_topic, json.dumps({"price": None}), retain=False, qos=0)
        payload = {"error": msg, **(extra or {})}
        self.client.publish(attr_topic, json.dumps(payload), retain=False, qos=0)

    async def loop(self):
        while True:
            try:
                if self.run_time:
                    now = datetime.now()
                    target = datetime.combine(now.date(), self.run_time)
                    if now >= target:
                        target = target + timedelta(days=1)
                    wait = (target - now).total_seconds()
                    print(f"[addon] Volgende geplande run om {target.isoformat(timespec='minutes')}")
                    await asyncio.sleep(wait)
                    await self.scrape_once()
                    continue
                else:
                    await self.scrape_once()
                    await asyncio.sleep(self.scan_interval)
            except Exception as ex:
                print(f"[addon] scrape_once error: {ex}")
                await asyncio.sleep(30)

def try_float(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace(" ", "")
    if "," in s and "." in s:
        if s.find(".") < s.find(","):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def extract_price(html: str) -> tuple[float | None, str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", {"type": ["application/ld+json", "application/json"]}):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for obj in items:
            if not isinstance(obj, dict):
                continue
            offers = obj.get("offers")
            def _as_eur(val) -> float | None:
                # normale parse
                v = try_float(val)
                if v is None:
                    # string die puur digits is? mogelijk centen
                    if isinstance(val, str) and val.isdigit():
                        iv = int(val)
                        if iv >= 10000:   # typisch cents (>= 100 euro)
                            return iv / 100.0
                    return None
                # Als heel groot en origineel was int/str-digits → mogelijk centen
                if v >= 10000 and isinstance(val, (int,)) :
                    return v / 100.0
                return v

            if isinstance(offers, dict):
                raw = offers.get("price") or offers.get("lowPrice")
                currency = offers.get("priceCurrency") or "EUR"
                val = _as_eur(raw)
                if val is not None:
                    return val, currency, "jsonld"
            if "price" in obj:
                raw = obj.get("price")
                val = _as_eur(raw)
                if val is not None:
                    return val, obj.get("priceCurrency", "EUR"), "jsonld-root"
    for selector, attr in META_HINTS:
        el = soup.select_one(selector)
        if not el:
            continue
        raw = (el.get(attr) if attr else el.get_text(" ")).strip()
        m = PRICE_RE.search(raw)
        if m:
            return normalize_euro(m.group(1)), "EUR", f"selector:{selector}"
    text = soup.get_text(" ", strip=True)
    candidates = [normalize_euro(m.group(1)) for m in PRICE_RE.finditer(text)]
    candidates = [c for c in candidates if c is not None]
    if candidates:
        candidates.sort()
        return candidates[len(candidates)//2], "EUR", "text-fallback"
    return None, "EUR", "none"

def normalize_euro(num: str) -> float | None:
    s = num.strip().replace(" ", "")
    if "," in s and "." in s:
        if s.find(".") < s.find(","):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def derive_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None

def read_options() -> dict[str, Any]:
    with open("/data/options.json", "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    options = read_options()
    app = App(options)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    def stop_handler(signum, frame):
        loop.stop()
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    loop.create_task(app.loop())
    loop.run_forever()

if __name__ == "__main__":
    main()
