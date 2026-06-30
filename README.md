# 🥂 Cheap Business Class

Finds **business & first-class flights for cheap — cash or points** — by scraping the
top travel blogs into one phone-friendly board. Uses **Scrapling** (stealth fetch, gets
past Cloudflare) + feedparser. No paid API.

```
fetch_deals.py (laptop, Scrapling) → docs/deals.json → GitHub Pages (phone)
```

## How it works
- **Source: Google News RSS search**, date-filtered (`when:21d`), across three queries
  (cash business-class deals, award/points deals, first-class deals). This pulls *current*
  premium-cabin deal coverage from every travel site at once.
- **Freshness guarded**: anything older than `MAX_AGE_DAYS` (30) is dropped, and posts
  flagged `[Expired]` are skipped — so no stale fares.
- **Noise filtered**: reviews, rankings ("World's Best…"), and cabin explainers
  ("What's included") are removed; only items that look like a real deal are kept.
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
The biggest lesson was about **freshness**, and it nearly shipped a broken product. I
first chased each blog's dedicated `…/tag/business-class/feed/` RSS — they exist and are
pure business class, so they looked perfect. But when I sorted cheapest-first, the top
deals were *three and four years old*: those tag feeds are frozen archives, not live
feeds. Meanwhile the blogs' fresh general feeds barely contain any business class, and
their HTML listing pages are JavaScript-rendered (a plain fetch sees nothing). The fix
was switching the whole source to **Google News RSS search** with a `when:21d` filter
plus a hard 30-day cutoff in code — date-filtered at the source *and* defended again
locally. Two takeaways: (1) for any deals aggregator, recency is a correctness property,
not a nicety — assert it, don't assume it; and (2) when a clean-looking feed surprises
you, check the actual dates before trusting it. I also got bitten by naive price parsing
(grabbing the smallest number pulled taxes, so "€1605" showed as "$574") — fixed by
taking the *first* price in the title and keeping its real currency symbol.
