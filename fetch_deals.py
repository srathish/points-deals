#!/usr/bin/env python3
"""Find CHEAP BUSINESS / FIRST CLASS flights — cash or points — that are ACTUALLY CURRENT.

The blogs' own "business-class" RSS tags turned out to be frozen archives (posts years
old), and their fresh general feeds rarely contain premium-cabin deals. So the primary
source here is **Google News RSS search**, which is date-filtered (`when:NNd`) and pulls
recent business/first-class deal coverage across every travel site at once. We then:
  * drop anything older than MAX_AGE_DAYS (no more 3-year-old fares),
  * drop posts flagged [Expired],
  * keep only items that look like a deal (price, sale, award, miles…),
  * tag each as cash (a $/€/£ price is extracted) or points (miles/avios award).

Scrapling does the stealth fetch; feedparser parses. Writes docs/deals.json.
"""
import json, os, re, html, urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from scrapling.fetchers import Fetcher
import feedparser

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_AGE_DAYS = 30   # flight deals expire fast — never show anything older

def gnews(query):
    return ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query) +
            "&hl=en-US&gl=US&ceid=US:en")

# Date-filtered Google News searches — each returns recent business/first deal posts.
SOURCES = {
    "Cash deals":  gnews('"business class" (deal OR sale OR fare OR cheap OR "flash sale") when:21d'),
    "Award deals": gnews('("business class" OR "first class") (miles OR points OR award OR "sweet spot") when:21d'),
    "First class": gnews('"first class" (deal OR fare OR sale OR award) when:21d'),
}

BIZ_RX = re.compile(r"\b(business[- ]?class|first[- ]?class|premium cabin|premium economy|"
                    r"lie[- ]?flat|polaris|q\s?suites?|qsuite|la premi[eè]re|flagship first)\b", re.I)
# Looks like an actual deal (not a review / awards-ceremony / news piece).
DEALY_RX = re.compile(r"(deal|sale|fare|cheap|% off|percent off|flash|from \$|under \$|"
                      r"\bmiles\b|\bpoints\b|avios|award|sweet spot|redeem|mistake|error fare)", re.I)
# Ranking / review / explainer noise that mentions "award" or "sale" but isn't a deal.
NONDEAL_RX = re.compile(r"(what(?:'s|\s+is|s)?\s+included|red dot|skytrax|world'?s best|"
                        r"best business|\breview\b|\bwins?\b|ranking|ranked|voted|explained|"
                        r"guide to|everything you|what to know|history of|\bvs\.?\b|comparison|"
                        r"\beconomy\b.{0,40}\bbusiness class\b)", re.I)
POINTS_RX = re.compile(r"\b(points?|miles|avios|award|transfer bonus|redeem|redemption|"
                       r"\d+k\s*(?:miles|points)|sweet spot)\b", re.I)
CASH_RX = re.compile(r"([$€£]\s?\d|round[- ]?trip|fare sale|from \$\d|under \$\d|cash fare|"
                     r"\bsale\b|\bfare\b)", re.I)
PRICE_RX = re.compile(r"([$€£])\s?(\d{1,3}(?:,\d{3})|\d{3,5})\b")
EXPIRED_RX = re.compile(r"\[?\bexpired\b\]?", re.I)

def clean(text, n=240):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text).strip()
    text = re.sub(r"\s+", " ", text)
    return (text[:n] + "…") if len(text) > n else text

def split_source(title):
    """Google News titles end with ' - Publisher'; pull that out as the source."""
    if " - " in title:
        head, _, pub = title.rpartition(" - ")
        if 2 <= len(pub) <= 40:
            return head.strip(), pub.strip()
    return title, "Google News"

def to_iso(entry):
    for k in ("published", "updated"):
        if entry.get(k):
            try: return parsedate_to_datetime(entry[k]).astimezone(timezone.utc).isoformat()
            except Exception: pass
    return ""

def age_days(iso):
    if not iso: return None
    try: return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).days
    except Exception: return None

def first_price(text):
    for m in PRICE_RX.finditer(text or ""):
        try: v = int(m.group(2).replace(",", ""))
        except ValueError: continue
        if 100 <= v <= 20000:
            return m.group(1), v
    return None, None

def fetch(url):
    r = Fetcher.get(url, timeout=25, stealthy_headers=True, retries=2)
    body = getattr(r, "body", None)
    text = body.decode("utf-8", "ignore") if isinstance(body, (bytes, bytearray)) else str(body)
    return getattr(r, "status", None), text

deals, errors = [], []
for label, url in SOURCES.items():
    try:
        status, text = fetch(url)
        f = feedparser.parse(text)
        if not f.entries:
            errors.append(f"{label}: 0 entries (status {status})"); continue
        kept = 0
        for e in f.entries:
            raw = clean(e.get("title", ""), 200)
            if EXPIRED_RX.search(raw):           continue
            title, source = split_source(raw)
            summary = clean(e.get("summary", "") or e.get("description", ""))
            blob = f"{title} {summary}"
            if not BIZ_RX.search(blob):           continue   # must be premium cabin
            if not DEALY_RX.search(blob):         continue   # must look like a deal
            if NONDEAL_RX.search(blob):           continue   # drop reviews/rankings/explainers
            iso = to_iso(e)
            if (age_days(iso) or 999) > MAX_AGE_DAYS: continue
            sym, price = first_price(title) if first_price(title)[1] else first_price(summary)
            is_points = bool(POINTS_RX.search(blob))
            is_cash = price is not None or bool(CASH_RX.search(blob))
            if not is_points and not is_cash:     # a fare deal with no explicit signal
                is_cash = True
            deals.append({
                "source": source,
                "category": label,
                "title": title,
                "link": e.get("link", ""),
                "summary": summary,
                "published": iso,
                "price": price,
                "cur": sym or "$",
                "is_biz": True,
                "is_cash": is_cash,
                "is_points": is_points,
            })
            kept += 1
        print(f"  {label}: kept {kept} of {len(f.entries)} (status {status})")
    except Exception as ex:
        errors.append(f"{label}: {type(ex).__name__}: {ex}")
        print(f"  ERR {label}: {ex}")

# De-dupe by normalized title (same story surfaces under several queries).
seen, uniq = set(), []
for d in deals:
    k = re.sub(r"[^a-z0-9]", "", d["title"].lower())[:60]
    if k in seen: continue
    seen.add(k); uniq.append(d)
deals = uniq

# Priced cash deals first (cheapest up top), then recent award/points deals.
deals.sort(key=lambda d: d["published"], reverse=True)
deals.sort(key=lambda d: (d["price"] is None, d["price"] or 0))

out = {
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    "count": len(deals),
    "max_age_days": MAX_AGE_DAYS,
    "sources": sorted({d["source"] for d in deals}),
    "errors": errors,
    "deals": deals,
}
os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
json.dump(out, open(os.path.join(HERE, "docs", "deals.json"), "w"), indent=2)
print(f"\nWrote {len(deals)} current business-class deals "
      f"({sum(d['is_cash'] for d in deals)} cash, "
      f"{sum(d['is_points'] for d in deals)} points, "
      f"max age {MAX_AGE_DAYS}d) -> docs/deals.json")
if errors: print("errors:", errors)
