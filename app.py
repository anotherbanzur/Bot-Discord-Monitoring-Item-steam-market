import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

ITEM_URLS = [
    "https://steamcommunity.com/market/listings/3678970/Frozen%20Orb%20(Arcana)%20A",
    "https://steamcommunity.com/market/listings/3678970/Knight%20Boots%20(Arcana)%20A",
    "https://steamcommunity.com/market/listings/3678970/Empire%2050th%20Anniversary%20Coin",
]


def parse_item_name(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    raw_path = urllib.parse.unquote(parsed.path)
    segments = [segment for segment in raw_path.split("/") if segment]
    if len(segments) >= 2 and segments[0] == "market" and segments[1] == "listings":
        return segments[-1]
    return raw_path.split("/")[-1]


def parse_app_id(url: str) -> str:
    match = re.search(r"/listings/([0-9]+)", url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not find app id in URL: {url}")


def parse_price_to_decimal(price_text: str) -> Decimal:
    cleaned = (price_text or "").replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned.lower() in {"tidak tersedia", "n/a"}:
        raise ValueError("Price unavailable")
    return Decimal(cleaned)


def get_idr_exchange_rate() -> Decimal:
    env_rate = os.getenv("IDR_EXCHANGE_RATE", "").strip()
    if env_rate:
        return Decimal(env_rate)

    try:
        request = urllib.request.Request(
            "https://api.exchangerate.host/latest?base=USD&symbols=IDR",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
        rate = payload.get("rates", {}).get("IDR")
        if rate:
            return Decimal(str(rate))
    except Exception:
        pass

    return Decimal("16000")


def format_idr(amount: Decimal) -> str:
    return f"Rp {amount.quantize(Decimal('1')).to_eng_string()}"


def fetch_price(url: str, exchange_rate: Decimal) -> dict:
    item_name = parse_item_name(url)
    app_id = parse_app_id(url)
    encoded_name = urllib.parse.quote(item_name)
    endpoint = f"https://steamcommunity.com/market/priceoverview/?currency=1&appid={app_id}&market_hash_name={encoded_name}"

    request = urllib.request.Request(
        endpoint,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )

    retry = 0
    while retry < 5:
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = 10 + retry * 5
                print(f"Rate limited by Steam (429). Retrying in {wait} seconds...")
                time.sleep(wait)
                retry += 1
                continue
            raise
        except urllib.error.URLError as exc:
            wait = 5 + retry * 5
            print(f"Network error: {exc}. Retrying in {wait} seconds...")
            time.sleep(wait)
            retry += 1
            continue
    else:
        raise RuntimeError("Failed to fetch Steam price after retries")

    if not payload.get("success"):
        raise RuntimeError(payload.get("message", "Steam did not return a valid price payload"))

    price = payload.get("lowest_price") or payload.get("median_price") or "Tidak tersedia"
    volume = payload.get("volume", "Tidak tersedia")

    price_idr = "Tidak tersedia"
    if price != "Tidak tersedia":
        try:
            usd_value = parse_price_to_decimal(price)
            price_idr = format_idr(usd_value * exchange_rate)
        except (InvalidOperation, ValueError):
            price_idr = "Tidak tersedia"

    return {
        "name": item_name,
        "price": price,
        "price_idr": price_idr,
        "volume": volume,
        "url": url,
    }


def send_to_discord(webhook_url: str, message: str) -> None:
    payload = json.dumps({"content": message}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 204:
                raise RuntimeError(f"Discord returned unexpected status: {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Discord webhook rejected the request ({exc.code}): {detail}"
        ) from exc


def run_once() -> None:
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    exchange_rate = get_idr_exchange_rate()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [f"Steam Market Monitor - {timestamp}"]
    lines.append(f"USD to IDR rate: {format_idr(exchange_rate)}")
    for url in ITEM_URLS:
        try:
            data = fetch_price(url, exchange_rate)
            lines.append(f"- {data['name']}: {data['price']} | {data['price_idr']} | volume: {data['volume']}")
        except Exception as exc:
            lines.append(f"- {parse_item_name(url)}: error - {exc}")
        time.sleep(5 + random.random() * 5)

    message = "\n".join(lines)
    print(message)

    if webhook_url:
        send_to_discord(webhook_url, message)
        print("Discord notification sent.")
    else:
        print("No DISCORD_WEBHOOK_URL configured. Skipping Discord send.")


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        while True:
            try:
                run_once()
            except Exception as exc:
                print(f"Loop error: {exc}")
            time.sleep(1800)
