#!/usr/bin/env python3
"""Find CHEAP BUSINESS / FIRST CLASS flights — cash or points — by scraping the top
travel blogs with Scrapling (stealth fetch, gets past Cloudflare) + feedparser.

Strategy:
  * Dedicated premium-cabin feeds (Fly4Free + God Save the Points "business-class"
    tags) — every item is treated as business class.
  * General points/miles + flight-deal blogs — kept for award "sweet spots" and cash
    fare drops, filtered down to premium-cabin posts by keyword.

Each deal is tagged so the phone page can filter:
  is_biz   — business / first / premium-cabin
  is_cash  — has a cash price (a $/€/£ amount is extracted into `price`)
  is_points— bookable with miles/points/avios (award sweet spot)
Writes docs/deals.json.
"""
import json, os, re, html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from scrapling.fetchers import Fetcher
import feedparser

HERE = os.path.dirname(os.path.abspath(__file__))

# name -> (url, force_biz). force_biz=True means a dedicated business-class feed
# where every item counts as premium cabin regardless of wording.
FEEDS = {
    "Fly4Free · Business":         ("https://www.fly4free.com/tag/business-class/feed/", True),
    "God Save the Points · Biz":   ("https://www.godsavethepoints.com/tag/business-class/feed/", True),
    # General blogs — mined for premium-cabin cash drops + award sweet spots:
    "The Flight Deal":             ("https://www.theflightdeal.com/feed/", False),
    "One Mile at a Time":          ("https://onemileatatime.com/feed/", False),
    "View from the Wing":          ("https://viewfromthewing.com/feed/", False),
    "The Points Guy":              ("https://thepointsguy.com/feed/", False),
    "Frequent Miler":              ("https://frequentmiler.com/feed/", False),
    "Thrifty Traveler":            ("https://thriftytraveler.com/feed/", False),
}

# Premium-cabin signal.
BIZ_RX = re.compile(r"\b(business[- ]?class|biz class|first[- ]?class|premium cabin|"
                    r"premium economy|lie[- ]?flat|polaris|q\s?suites?|qsuite|"
                    r"la premi[eè]re|flagship first|residence|the apartment)\b", re.I)
# Bookable with miles/points.
POINTS_RX = re.compile(r"\b(points?|miles|avios|award|transfer bonus|redeem|redemption|"
                       r"\d+k\s*(?:miles|points)|sweet spot|membership rewards|"
                       r"ultimate rewards|amex|chase points)\b", re.I)
# Cash-fare signal (a real fare sale, not an award post).
CASH_RX = re.compile(r"([$€£]\s?\d|round[- ]?trip|r/t\b|fare sale|from \$\d|cash fare)", re.I)
# Extract a plausible fare price (100–20000) so we can show & sort by it.
PRICE_RX = re.compile(r"([$€£])\s?(\d{1,3}(?:,\d{3})|\d{3,5})\b")

def clean(text, n=240):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text).strip()
    text = re.sub(r"\s+", " ", text)
    return (text[:n] + "…") if len(text) > n else text

def to_iso(entry):
    for k in ("published", "updated"):
        v = entry.get(k)
        if v:
            try: return parsedate_to_datetime(v).astimezone(timezone.utc).isoformat()
            except Exception: pass
    if entry.get("published_parsed"):
        import calendar
        return datetime.fromtimestamp(calendar.timegm(entry.published_parsed), timezone.utc).isoformat()
    return ""

def first_price(text):
    """First plausible (symbol, value) fare in `text` — titles lead with the headline fare."""
    for m in PRICE_RX.finditer(text or ""):
        try: v = int(m.group(2).replace(",", ""))
        except ValueError: continue
        if 100 <= v <= 20000:
            return m.group(1), v
    return None, None

def extract_price(title, summary):
    """Prefer the headline price in the title; fall back to the summary."""
    sym, val = first_price(title)
    if val is None:
        sym, val = first_price(summary)
    return sym, val

def fetch(url):
    r = Fetcher.get(url, timeout=25, stealthy_headers=True, retries=2)
    body = getattr(r, "body", None)
    text = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else str(body)
    return getattr(r, "status", None), text

deals, errors = [], []
for source, (url, force_biz) in FEEDS.items():
    try:
        status, text = fetch(url)
        f = feedparser.parse(text)
        if not f.entries:
            errors.append(f"{source}: 0 entries (status {status})"); continue
        kept = 0
        for e in f.entries[:25]:
            title = clean(e.get("title", ""), 160)
            summary = clean(e.get("summary", "") or e.get("description", ""))
            blob = f"{title} {summary}"
            is_biz = force_biz or bool(BIZ_RX.search(blob))
            if not is_biz:
                continue  # this tool only cares about premium cabin
            cur, price = extract_price(title, summary)
            is_points = bool(POINTS_RX.search(blob))
            is_cash = price is not None or bool(CASH_RX.search(blob))
            deals.append({
                "source": source,
                "title": title,
                "link": e.get("link", ""),
                "summary": summary,
                "published": to_iso(e),
                "price": price,
                "cur": cur or "$",
                "is_biz": True,
                "is_cash": is_cash,
                "is_points": is_points,
            })
            kept += 1
        print(f"  {source}: {kept} business of {len(f.entries)} (status {status})")
    except Exception as ex:
        errors.append(f"{source}: {type(ex).__name__}: {ex}")
        print(f"  ERR {source}: {ex}")

# De-dupe by link (same deal can appear in multiple feeds).
seen, uniq = set(), []
for d in deals:
    k = d["link"] or d["title"]
    if k in seen: continue
    seen.add(k); uniq.append(d)
deals = uniq

# Cash deals with a price first (cheapest up top), then recent points sweet spots.
deals.sort(key=lambda d: d["published"], reverse=True)
deals.sort(key=lambda d: (d["price"] is None, d["price"] or 0))  # priced, cheapest first

out = {
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "count": len(deals),
    "sources": list(FEEDS.keys()),
    "errors": errors,
    "deals": deals,
}
os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "docs", "deals.json"), "w"), indent=2)
print(f"\nWrote {len(deals)} business-class deals "
      f"({sum(d['is_cash'] for d in deals)} cash, "
      f"{sum(d['is_points'] for d in deals)} points, "
      f"{sum(d['price'] is not None for d in deals)} priced) -> docs/deals.json")
if errors: print("errors:", errors)
