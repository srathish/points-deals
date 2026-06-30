# 🥂 Cheap Business Class

Finds **business & first-class flights for cheap — cash or points** — by scraping the
top travel blogs into one phone-friendly board. Uses **Scrapling** (stealth fetch, gets
past Cloudflare) + feedparser. No paid API.

```
fetch_deals.py (laptop, Scrapling) → docs/deals.json → GitHub Pages (phone)
```

## How it works
- **Dedicated premium-cabin feeds** — Fly4Free and God Save the Points "business-class"
  tags; every item is a business/first deal.
- **General points/miles + flight blogs** — One Mile at a Time, View from the Wing,
  The Points Guy, Frequent Miler, The Flight Deal, Thrifty Traveler — filtered down to
  premium-cabin posts by keyword (award sweet spots + cash fare drops).
- Each deal is tagged **cash** (a $/€/£ price is extracted and shown) or **points**
  (miles/avios award), and the page sorts cheapest-first.

## Refresh
```bash
./venv/bin/python3 fetch_deals.py
git add docs/deals.json && git commit -m "refresh deals" && git push
```

- **Live page:** https://srathish.github.io/points-deals/
- Filter chips: **🥂 All business · 💵 Cash · ⭐ Points**. Sort by **Cheapest / Newest**.

## What I learned
The hard part wasn't scraping — it was *signal*. Keyword-filtering general blog feeds for
"business class" only surfaced a handful of real deals, so I went hunting for each blog's
dedicated `…/tag/business-class/feed/` URL. Most don't exist or 404, but Fly4Free's and
God Save the Points' do, and they carry the bulk of the good fares. I also got bitten by
naive price extraction: grabbing the *smallest* number in a post pulled taxes or a
secondary route's fare, so "€1605 to Bangkok" displayed as "$574." Pulling the *first*
price from the **title** (where these blogs lead with the headline fare) and keeping the
real currency symbol fixed it. Lesson: for aggregators, finding the highest-signal source
beats writing a cleverer filter over a noisy one.
