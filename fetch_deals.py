#!/usr/bin/env python3
"""Scrape points/miles + flight deals from the top travel blogs using Scrapling
(stealth fetch — gets past Cloudflare) + feedparser, and write docs/deals.json for
the phone page.

Each item is tagged so the page can filter by category:
  is_deal   — an actual deal/redemption (not just news)
  is_flight — about flights / airfare
  is_biz    — a premium-cabin deal (business / first / premium economy)
"""
import json, os, re, html
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from scrapling.fetchers import Fetcher
import feedparser

HERE = os.path.dirname(os.path.abspath(__file__))

# Points/miles blogs + flight-deal blogs (mistake/error fares, premium-cabin alerts).
FEEDS = {
    "Frequent Miler":     "https://frequentmiler.com/feed/",
    "The Points Guy":     "https://thepointsguy.com/feed/",
    "Doctor of Credit":   "https://www.doctorofcredit.com/feed/",
    "One Mile at a Time": "https://onemileatatime.com/feed/",
    "View from the Wing": "https://viewfromthewing.com/feed/",
    "God Save the Points":"https://www.godsavethepoints.com/feed/",
    "Thrifty Traveler":   "https://thriftytraveler.com/feed/",
    # Flight-deal focused:
    "The Flight Deal":    "https://www.theflightdeal.com/feed/",
    "Fly4Free":           "https://www.fly4free.com/feed/",
}

# Flags a post as an actual deal/redemption (not just news).
DEAL_RX = re.compile(r"\b(deal|deals|sale|bonus|transfer bonus|award|miles|points|fare|"
                     r"mistake fare|error fare|sweet spot|% off|percent off|discount|"
                     r"promo|promotion|offer|cheap|book now|limited time|flash)\b", re.I)

# Flags a post as being about flights / airfare specifically.
FLIGHT_RX = re.compile(r"\b(flight|flights|fare|fares|airfare|airline|airlines|"
                       r"mistake fare|error fare|nonstop|non-stop|round[- ]?trip|"
                       r"economy|premium economy|business class|first class|"
                       r"award (?:seat|seats|flight|flights|ticket|space)|"
                       r"cents? per (?:mile|point)|\d+k?\s*(?:miles|points))\b", re.I)

# Flags a premium-cabin deal (business / first / premium economy / lie-flat product).
BIZ_RX = re.compile(r"\b(business[- ]?class|biz class|first[- ]?class|premium cabin|"
                    r"premium economy|lie[- ]?flat|polaris|q\s?suites?|qsuite|"
                    r"la premi[eè]re|flagship first|residence|the apartment)\b", re.I)

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

def fetch(url):
    r = Fetcher.get(url, timeout=25, stealthy_headers=True, retries=2)
    body = getattr(r, "body", None)
    text = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else str(body)
    return getattr(r, "status", None), text

deals, errors = [], []
for source, url in FEEDS.items():
    try:
        status, text = fetch(url)
        f = feedparser.parse(text)
        if not f.entries:
            errors.append(f"{source}: 0 entries (status {status})"); continue
        for e in f.entries[:20]:
            title = clean(e.get("title", ""), 160)
            summary = clean(e.get("summary", "") or e.get("description", ""))
            blob = f"{title} {summary}"
            is_biz = bool(BIZ_RX.search(blob))
            deals.append({
                "source": source,
                "title": title,
                "link": e.get("link", ""),
                "summary": summary,
                "published": to_iso(e),
                "is_deal": bool(DEAL_RX.search(blob)),
                "is_flight": bool(FLIGHT_RX.search(blob)) or is_biz,
                "is_biz": is_biz,
            })
        print(f"  {source}: {len(f.entries)} entries (status {status})")
    except Exception as ex:
        errors.append(f"{source}: {type(ex).__name__}: {ex}")
        print(f"  ERR {source}: {ex}")

# Deal-flagged first, then by recency.
deals.sort(key=lambda d: d["published"], reverse=True)
deals.sort(key=lambda d: d["is_deal"], reverse=True)

out = {
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "count": len(deals),
    "sources": list(FEEDS.keys()),
    "errors": errors,
    "deals": deals,
}
os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "docs", "deals.json"), "w"), indent=2)
print(f"\nWrote {len(deals)} items "
      f"({sum(d['is_deal'] for d in deals)} deals, "
      f"{sum(d['is_flight'] for d in deals)} flight, "
      f"{sum(d['is_biz'] for d in deals)} business) -> docs/deals.json")
if errors: print("errors:", errors)
