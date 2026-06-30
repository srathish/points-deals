# 💳 Points & Miles Deals

Aggregates the top points/miles travel blogs into one phone-friendly deals board.
Uses **Scrapling** (stealth fetch — gets past Cloudflare on sites like The Points Guy) + feedparser.

```
fetch_deals.py (laptop, Scrapling) → docs/deals.json → GitHub Pages (phone)
```

## Sources
Frequent Miler · The Points Guy · Doctor of Credit · One Mile at a Time · View from the Wing · God Save the Points · Thrifty Traveler

## Refresh
```bash
./venv/bin/python3 fetch_deals.py
git add docs/deals.json && git commit -m "refresh deals" && git push
```

- **Live page:** https://srathish.github.io/points-deals/
- 🔥 "Deals only" filters to posts about bonuses/awards/sales; toggle "All posts" for everything.
