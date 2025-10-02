# Jaipur Auction Finder — Free Starter

A zero-cost Jaipur-only foreclosure/auction aggregator.  
**Stack:** GitHub Pages (hosting) + GitHub Actions (scheduler) + Python (scraper) + Leaflet (map).

## Quick start
1. Create a new GitHub repo and upload these files. Or push:
   ```bash
   git init
   git remote add origin <your-repo-url>
   git add .
   git commit -m "init"
   git branch -M main
   git push -u origin main
   ```
2. **Enable Pages:** Repo → Settings → Pages → Build from `main` → Save.  
   Your site will serve `index.html` from the root.
3. **Run the workflow once:** Actions → *Scrape Jaipur Auctions* → Run workflow.
4. Check `data/listings.json` and your Pages site. The seed listing will render immediately; cron will refresh twice a day.

## Where the data comes from (initial sources)
- eAuctionsIndia Jaipur city page (parse-friendly).
- Bank DRT (Jaipur filter).
- MSTC forthcoming table (lines that mention Rajasthan/Jaipur).

> Note: We only keep light metadata + link back. Always verify directly on source pages.

## Add more sources later
- **IBAPI (Govt portal):** Add a Playwright/Requests form search for Rajasthan/Jaipur and merge into `scraper/scrape.py`.
- **RERA recoveries via MSTC:** Watch for Rajasthan RERA → MSTC notices; add a small parser.

## Optional: Telegram alerts (free)
Add a second step in the workflow after commit to post new items to your Telegram channel using a bot token + chat id stored as repo secrets.

## Disclaimer
Bank auctions are typically on “AS‑IS‑WHERE‑IS / AS‑IS‑WHAT‑IS” basis; buyers must independently verify title, dues and possession. This project links to public notices and does not guarantee completeness or accuracy.
