import json
from pathlib import Path
from datetime import datetime

from lib import quality_filter, backfill_geo, dedup
from sources.eai import get_listings as eai_list
from sources.bankdrt import get_listings as drt_list
from sources.mstc import get_listings as mstc_list
from sources.bankeauctions import get_listings as bae_list
from sources.ibapi_playwright import get_listings as ibapi_list

def main():
    all_rows = []
    all_rows += eai_list()
    all_rows += drt_list()
    all_rows += mstc_list()
    all_rows += bae_list()
    try:
        all_rows += ibapi_list()  # headless; may return 0 if selectors drift
    except Exception as e:
        print("IBAPI spider failed (non-fatal):", e)

    cleaned = quality_filter(all_rows)
    cleaned = dedup(cleaned)
    cleaned = backfill_geo(cleaned)

    Path("data").mkdir(parents=True, exist_ok=True)
    Path("data/listings.json").write_text(json.dumps(cleaned, ensure_ascii=False, indent=2))
    print(f"Wrote {len(cleaned)} listings at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
