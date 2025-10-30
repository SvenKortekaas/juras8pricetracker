from __future__ import annotations

import asyncio
import json
import re
import signal
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Any

import httpx
import paho.mqtt.client as mqtt
from bs4 import BeautifulSoup

from logging_utils import get_logger, setup_logging

PRICE_RE = re.compile(
    r"(?<!\d)(?:\u20ac\s*|\bEUR\s*)(\d{1,4}(?:[.,]\d{3})*(?:[.,]\d{2})?)",
    re.IGNORECASE,
)
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
    price_divisor: float | None = None


class App:
    def __init__(self, options: dict[str, Any], loop: asyncio.AbstractEventLoop):
        self.logger = get_logger("addon").bind(component="app")
        self.async_loop = loop
        self.scan_interval = int(options.get("scan_interval", 1800))
        self.run_time_str = options.get("run_time")
        self.run_time: dtime | None = None
        if self.run_time_str:
            try:
                hours, minutes = map(int, self.run_time_str.split(":"))
                self.run_time = dtime(hours, minutes)
            except Exception:
                self.logger.warning(
                    "Invalid run_time value; expected HH:MM.",
                    extra={"run_time": self.run_time_str},
                )

        raw_product = (options.get("product_name") or "").strip()
        self.product_name = raw_product or "Website Price Tracker"

        self.base_topic = options.get("base_topic", "price_tracker").strip().strip("/")
        if not self.base_topic:
            self.base_topic = "price_tracker"
        self.logger = self.logger.bind(
            base_topic=self.base_topic,
            product_name=self.product_name,
        )

        self.force_command_topic = f"{self.base_topic}/command/refresh"
        self.refresh_discovery_topic = f"homeassistant/button/{self.base_topic}/refresh/config"

        self.mqtt_host = options.get("mqtt_host", "core-mosquitto")
        self.mqtt_port = int(options.get("mqtt_port", 1883))
        self.mqtt_username = options.get("mqtt_username") or None
        self.mqtt_password = options.get("mqtt_password") or None
        self.min_price = try_float(options.get("min_price")) or 0.0
        self.max_price = try_float(options.get("max_price")) or 1e9
        self.sites = [
            Site(
                s["id"],
                s["url"],
                s.get("title"),
                s.get("headers", {}),
                try_float(s.get("price_divisor")) or None,
            )
            for s in options.get("sites", [])
        ]

        self.force_event: asyncio.Event | None = None
        self.scrape_lock: asyncio.Lock | None = None
        self._pending_force_requests = 0

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=f"{self.base_topic}_addon"
        )
        if self.mqtt_username:
            self.client.username_pw_set(self.mqtt_username, self.mqtt_password or "")
        self.client.enable_logger(get_logger("addon.mqtt").logger)
        self.client.on_connect = self._handle_connect
        self.client.on_message = self._handle_message
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
        except Exception as exc:
            self.logger.error(
                "Failed to connect to MQTT broker.",
                extra={"mqtt_host": self.mqtt_host, "mqtt_port": self.mqtt_port},
                exc_info=exc,
            )
            raise
        self.client.loop_start()

        self.device = {
            "identifiers": [f"{self.base_topic}_addon"],
            "name": self.product_name,
            "manufacturer": "Custom",
            "model": "Home Assistant Add-on",
        }
        mode = "scheduled" if self.run_time else "interval"
        self.logger.info(
            "Application initialised.",
            extra={
                "mode": mode,
                "run_time": self.run_time_str,
                "scan_interval": self.scan_interval,
                "sites": len(self.sites),
                "min_price": self.min_price,
                "max_price": self.max_price,
                "mqtt_host": self.mqtt_host,
                "mqtt_port": self.mqtt_port,
                "product_name": self.product_name,
            },
        )
        self.publish_refresh_button_discovery()

    def publish_discovery(self, site: Site):
        obj_id = f"{self.base_topic}_{site.id}".lower()
        disc_topic = f"homeassistant/sensor/{self.base_topic}/{site.id}/config"
        state_topic = f"{self.base_topic}/state/{site.id}"
        attr_topic = f"{self.base_topic}/attr/{site.id}"
        payload = {
            "name": f"{self.product_name} {site.title or site.id}",
            "unique_id": obj_id,
            "state_topic": state_topic,
            "json_attributes_topic": attr_topic,
            "device_class": "monetary",
            "state_class": "measurement",
            "unit_of_measurement": "\u20ac",
            "value_template": "{{ value_json.price }}",
            "device": self.device,
        }
        self.logger.debug(
            "Publishing MQTT discovery payload.",
            extra={"site": site.id, "topic": disc_topic},
        )
        self.client.publish(disc_topic, json.dumps(payload), retain=True, qos=1)

    def publish_refresh_button_discovery(self):
        payload = {
            "name": f"{self.product_name} Refresh",
            "unique_id": f"{self.base_topic}_refresh_button",
            "command_topic": self.force_command_topic,
            "payload_press": "PRESS",
            "device": self.device,
            "icon": "mdi:update",
            "entity_category": "config",
        }
        self.logger.debug(
            "Publishing MQTT discovery payload for refresh button.",
            extra={"topic": self.refresh_discovery_topic},
        )
        self.client.publish(
            self.refresh_discovery_topic,
            json.dumps(payload),
            retain=True,
            qos=1,
        )

    async def scrape_once(self):
        if not self.sites:
            self.logger.warning("No sites configured; skipping scrape cycle.")
            return

        self.logger.info(
            "Starting scrape cycle.",
            extra={"site_count": len(self.sites)},
        )
        async with httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
            },
            follow_redirects=True,
            timeout=25,
        ) as client:
            for site in self.sites:
                site_logger = self.logger.bind(site=site.id)
                try:
                    self.publish_discovery(site)
                    site_logger.debug("Fetching page.", extra={"url": site.url})
                    resp = await client.get(
                        site.url,
                        headers={**client.headers, **(site.headers or {})},
                    )
                    try_alt = resp.status_code in (403, 406)
                    resp.raise_for_status()
                    html = resp.text
                    status = resp.status_code
                    method_hint = "ok"
                except httpx.HTTPStatusError as error:
                    if try_alt:
                        site_logger.warning(
                            "Received blocking status; retrying with alternate headers.",
                            extra={"status": error.response.status_code},
                        )
                        alt_headers = {
                            "User-Agent": (
                                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
                                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                                "Version/16.5 Safari/605.1.15"
                            ),
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Sec-Fetch-Mode": "navigate",
                        }
                        response_retry = await client.get(
                            site.url,
                            headers={**alt_headers, **(site.headers or {})},
                        )
                        html = response_retry.text
                        status = response_retry.status_code
                        method_hint = "retry"
                    else:
                        site_logger.error(
                            "HTTP request failed after retries.",
                            extra={"status": error.response.status_code},
                        )
                        self.publish_error(site, f"HTTP {error.response.status_code}")
                        continue
                except Exception as exc:
                    site_logger.exception(
                        "Unexpected exception while fetching site.",
                        extra={"url": site.url},
                        exc_info=exc,
                    )
                    self.publish_error(site, f"{type(exc).__name__}: {exc}")
                    continue

                price, currency, method = extract_price(html)
                title = derive_title(html) or site.title or site.id

                if price is not None:
                    if site.price_divisor:
                        if site.price_divisor > 0:
                            price /= site.price_divisor
                            method += f"+div{site.price_divisor:g}"
                        else:
                            site_logger.warning(
                                "Configured price_divisor must be greater than 0.",
                                extra={"price_divisor": site.price_divisor},
                            )
                    if not (self.min_price <= price <= self.max_price):
                        fixed: float | None = None
                        if self.min_price <= price / 100.0 <= self.max_price:
                            fixed = price / 100.0
                            method += "+heuristic_div100"
                        elif self.min_price <= price / 10.0 <= self.max_price:
                            fixed = price / 10.0
                            method += "+heuristic_div10"

                        if fixed is not None:
                            price = fixed
                        else:
                            site_logger.warning(
                                "Price outside configured bounds.",
                                extra={
                                    "title": title,
                                    "raw_price": price,
                                    "method": method,
                                },
                            )
                            self.publish_error(
                                site,
                                "price_out_of_range",
                                extra={
                                    "title": title,
                                    "raw_price": price,
                                    "min": self.min_price,
                                    "max": self.max_price,
                                    "method": method,
                                },
                            )
                            continue
                else:
                    site_logger.warning(
                        "Failed to detect a price.",
                        extra={"method": method},
                    )

                state_topic = f"{self.base_topic}/state/{site.id}"
                attr_topic = f"{self.base_topic}/attr/{site.id}"
                site_logger.info(
                    "Publishing price update.",
                    extra={
                        "price": price,
                        "currency": currency or "EUR",
                        "method": f"{method}+{method_hint}",
                        "status_code": status,
                    },
                )
                self.client.publish(
                    state_topic,
                    json.dumps({"price": price}),
                    retain=False,
                    qos=0,
                )
                self.client.publish(
                    attr_topic,
                    json.dumps(
                        {
                            "title": title,
                            "url": site.url,
                            "currency": currency or "EUR",
                            "source_method": f"{method}+{method_hint}",
                            "status_code": status,
                        }
                    ),
                    retain=False,
                    qos=0,
                )

        self.logger.info("Scrape cycle completed.")

    def publish_error(self, site: Site, msg: str, extra: dict[str, Any] | None = None):
        attr_topic = f"{self.base_topic}/attr/{site.id}"
        state_topic = f"{self.base_topic}/state/{site.id}"
        payload = {"error": msg, **(extra or {})}
        self.logger.error(
            "Publishing error state.",
            extra={"site": site.id, "error": msg, **(extra or {})},
        )
        self.client.publish(
            state_topic,
            json.dumps({"price": None}),
            retain=False,
            qos=0,
        )
        self.client.publish(
            attr_topic,
            json.dumps(payload),
            retain=False,
            qos=0,
        )

    def _handle_connect(
        self,
        client: mqtt.Client,
        userdata,
        flags,
        reason_code: mqtt.ReasonCodes,
        properties=None,
    ):
        reason_value = getattr(reason_code, "value", reason_code)
        try:
            reason_int = int(reason_value)
        except (TypeError, ValueError):
            reason_int = None
        reason_name = getattr(reason_code, "name", str(reason_code))
        self.logger.info(
            "Connected to MQTT broker.",
            extra={
                "reason_code": reason_int,
                "reason_name": reason_name,
                "command_topic": self.force_command_topic,
            },
        )
        result, mid = client.subscribe(self.force_command_topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            self.logger.error(
                "Failed to subscribe to refresh command topic.",
                extra={"result": result, "mid": mid, "topic": self.force_command_topic},
            )
        else:
            self.logger.debug(
                "Subscribed to refresh command topic.",
                extra={"mid": mid, "topic": self.force_command_topic},
            )

    def _handle_message(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage):
        topic = message.topic
        if topic != self.force_command_topic:
            return
        payload = (message.payload or b"").decode("utf-8", errors="ignore").strip()
        self.logger.info(
            "Force refresh command received.",
            extra={"payload": payload or "<empty>"},
        )
        try:
            self.async_loop.call_soon_threadsafe(self._apply_force_request)
        except RuntimeError:
            # Loop already closed; ignore.
            self.logger.warning(
                "Async loop closed; ignoring force refresh command.",
            )

    def _apply_force_request(self):
        if self.force_event is not None:
            self.force_event.set()
        else:
            self._pending_force_requests += 1

    async def _run_scrape(self, reason: str):
        if self.scrape_lock is None:
            self.scrape_lock = asyncio.Lock()
        async with self.scrape_lock:
            if reason == "force":
                self.logger.info(
                    "Executing scrape in response to MQTT refresh request.",
                    extra={"product_name": self.product_name},
                )
            await self.scrape_once()

    async def _wait_for_force(self, timeout: float) -> bool:
        if self.force_event is None:
            self.force_event = asyncio.Event()
        if self.force_event.is_set():
            self.force_event.clear()
            return True
        if timeout <= 0:
            return False
        sleep_task = asyncio.create_task(asyncio.sleep(timeout))
        force_task = asyncio.create_task(self.force_event.wait())
        done, pending = await asyncio.wait(
            {sleep_task, force_task}, return_when=asyncio.FIRST_COMPLETED
        )
        if force_task in done:
            self.force_event.clear()
            sleep_task.cancel()
            with suppress(asyncio.CancelledError):
                await sleep_task
            return True
        force_task.cancel()
        with suppress(asyncio.CancelledError):
            await force_task
        return False

    async def loop(self):
        if self.force_event is None:
            self.force_event = asyncio.Event()
        if self._pending_force_requests:
            self.force_event.set()
            self._pending_force_requests = 0
        if self.scrape_lock is None:
            self.scrape_lock = asyncio.Lock()

        while True:
            try:
                if self.run_time:
                    now = datetime.now()
                    target = datetime.combine(now.date(), self.run_time)
                    if now >= target:
                        target = target + timedelta(days=1)
                    wait_seconds = (target - now).total_seconds()
                    self.logger.info(
                        "Scheduled execution calculated.",
                        extra={"next_run": target.isoformat(timespec="minutes")},
                    )
                    if await self._wait_for_force(wait_seconds):
                        await self._run_scrape(reason="force")
                        continue
                    await self._run_scrape(reason="scheduled")
                    continue
                await self._run_scrape(reason="scheduled")
                while True:
                    if await self._wait_for_force(self.scan_interval):
                        await self._run_scrape(reason="force")
                    else:
                        break
            except Exception as exc:
                self.logger.exception(
                    "scrape_once raised an exception; backing off.",
                    exc_info=exc,
                )
                await asyncio.sleep(30)


def try_float(value: Any) -> float | None:
    if value is None:
        return None
    candidate = str(value).strip().replace(" ", "")
    if "," in candidate and "." in candidate:
        if candidate.find(".") < candidate.find(","):
            candidate = candidate.replace(".", "").replace(",", ".")
        else:
            candidate = candidate.replace(",", "")
    else:
        candidate = candidate.replace(".", "").replace(",", ".")
    try:
        return float(candidate)
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
                parsed = try_float(val)
                if parsed is None:
                    if isinstance(val, str) and val.isdigit():
                        integer_value = int(val)
                        if integer_value >= 10000:
                            return integer_value / 100.0
                    return None
                if parsed >= 10000 and isinstance(val, int):
                    return parsed / 100.0
                return parsed

            if isinstance(offers, dict):
                raw = offers.get("price") or offers.get("lowPrice")
                currency = offers.get("priceCurrency") or "EUR"
                converted = _as_eur(raw)
                if converted is not None:
                    return converted, currency, "jsonld"
            if "price" in obj:
                raw = obj.get("price")
                converted = _as_eur(raw)
                if converted is not None:
                    return converted, obj.get("priceCurrency", "EUR"), "jsonld-root"

    for selector, attr in META_HINTS:
        element = soup.select_one(selector)
        if not element:
            continue
        raw_value = (element.get(attr) if attr else element.get_text(" ")).strip()
        match = PRICE_RE.search(raw_value)
        if match:
            return normalize_euro(match.group(1)), "EUR", f"selector:{selector}"

    text = soup.get_text(" ", strip=True)
    candidates = [normalize_euro(match.group(1)) for match in PRICE_RE.finditer(text)]
    candidates = [candidate for candidate in candidates if candidate is not None]
    if candidates:
        candidates.sort()
        return candidates[len(candidates) // 2], "EUR", "text-fallback"
    return None, "EUR", "none"


def normalize_euro(num: str) -> float | None:
    candidate = num.strip().replace(" ", "")
    if "," in candidate and "." in candidate:
        if candidate.find(".") < candidate.find(","):
            candidate = candidate.replace(".", "").replace(",", ".")
        else:
            candidate = candidate.replace(",", "")
    else:
        candidate = candidate.replace(".", "").replace(",", ".")
    try:
        return float(candidate)
    except Exception:
        return None


def derive_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def read_options() -> dict[str, Any]:
    with open("/data/options.json", "r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    options = read_options()
    setup_logging(level=options.get("log_level"))
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = App(options, loop)
    loop_logger = get_logger("addon.loop")

    def handle_async_exception(loop_obj, context):
        exc = context.get("exception")
        message = context.get("message", "Asyncio exception")
        if exc:
            loop_logger.error(message, extra={"source": context.get("future")}, exc_info=exc)
        else:
            loop_logger.error(message)

    loop.set_exception_handler(handle_async_exception)

    def stop_handler(signum, frame):
        loop_logger.info("Received stop signal; shutting down.", extra={"signal": signum})
        with suppress(Exception):
            app.client.loop_stop()
        loop.stop()

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    loop.create_task(app.loop())
    loop.run_forever()


if __name__ == "__main__":
    main()
