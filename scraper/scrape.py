import re, json, hashlib, sys, time
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as dtparse

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JaipurAuctionBot/1.0; +https://github.com/you)"}

# --- Jaipur colonies/areas (aliases + normalised) ---
COLONY_ALIASES = {
    # West
    "vaishali nagar":"Vaishali Nagar", "vaishalinagar":"Vaishali Nagar",
    "queens road":"Queens Road", "queen's road":"Queens Road", "queen road":"Queens Road",
    "ajmer road":"Ajmer Road", "ajmer rd":"Ajmer Road",
    "chitrakoot":"Chitrakoot", "niwaru road":"Niwaru Road", "sodala":"Sodala", "bais godam":"Bais Godam",
    "jhotwara":"Jhotwara", "hathoj":"Hathoj",
    # South
    "mansarovar":"Mansarovar", "new sanganer road":"New Sanganer Road",
    "dcm":"DCM", "patalon ki dhani":"Patalon Ki Dhani",
    "pratap nagar":"Pratap Nagar", "pratab nagar":"Pratap Nagar",
    "sanganer":"Sanganer", "tonk road":"Tonk Road", "sitapura":"Sitapura",
    "jagatpura":"Jagatpura", "malviya nagar":"Malviya Nagar", "gom defence colony":"GOM Defence Colony",
    # Central
    "c-scheme":"C-Scheme", "c scheme":"C-Scheme",
    "bapu nagar":"Bapu Nagar", "ashok nagar":"Ashok Nagar", "mi road":"MI Road",
    "bani park":"Bani Park", "banipark":"Bani Park", "station road":"Station Road",
    # North/North-East
    "vidhyadhar nagar":"Vidhyadhar Nagar", "vidyadhar nagar":"Vidhyadhar Nagar", "v d nagar":"Vidhyadhar Nagar",
    "muralipura":"Muralipura", "vki":"VKI", "vki area":"VKI",
    "lal kothi":"Lal Kothi", "jawahar nagar":"Jawahar Nagar",
    # East
    "agrawal farm":"Agrawal Farm", "durgapura":"Durgapura",
    "gopalpura":"Gopalpura", "gopalpura bypass":"Gopalpura Bypass",
    # Others
    "amer":"Amer", "jal mahal":"Jal Mahal",
    "rajapark":"Raja Park", "raja park":"Raja Park",
    "hawa mahal":"Hawa Mahal",
    "sikar road":"Sikar Road", "delhi road":"Delhi Road",
    "jln marg":"JLN Marg", "j l n marg":"JLN Marg", "jawaharlal nehru marg":"JLN Marg",
}

# Optional map pins for common areas
GEO = {
    "Vaishali Nagar": (26.914, 75.748),
    "Mansarovar": (26.858, 75.770),
    "Ajmer Road": (26.885, 75.730),
    "Queens Road": (26.908, 75.760),
    "C-Scheme": (26.912, 75.809),
    "Jagatpura": (26.822, 75.836),
    "Pratap Nagar": (26.788, 75.824),
    "Sodala": (26.898, 75.787),
    "Bani Park": (26.928, 75.797),
    "Jhotwara": (26.955, 75.740),
    "Vidhyadhar Nagar": (26.954, 75.784),
    "Tonk Road": (26.861, 75.802),
    "Malviya Nagar": (26.853, 75.815),
    "Amer": (26.985, 75.851)
}

def normspace(s): 
    return re.sub(r"\s+", " ", (s or "")).strip()

def sha1key(*parts):
    raw = "|".join(normspace(p).lower() for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def parse_money(text):
    if not text: return None
    t = text.replace(",", "").replace("₹", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return int(float(m.group(1))) if m else None

def parse_dt(text):
    if not text: return None
    try:
        return dtparse(normspace(text), dayfirst=True).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None

def normalise_type(title):
    t = (title or "").lower()
    if any(k in t for k in ["flat", "apartment"]): return "Flat"
    if any(k in t for k in ["plot"]): return "Plot"
    if any(k in t for k in ["villa","house","independent"]): return "House"
    if any(k in t for k in ["shop","showroom","commercial","office","industrial","warehouse","godown"]): return "Commercial"
    if any(k in t for k in ["land"]): return "Land"
    return "Property"

def detect_locality(*texts):
    blob = (" ".join([normspace(x) for x in texts if x])).lower()
    for alias, proper in COLONY_ALIASES.items():
        if alias in blob:
            return proper
    if "jaipur" in blob:
        return "Jaipur"
    return None

# -------- SOURCE 1: eAuctionsIndia Jaipur (with pagination) --------
def scrape_eai():
    base = "https://www.eauctionsindia.com/city/jaipur"
    out, page, seen_urls = [], 1, set()
    while page <= 5:  # safety cap
        url = base if page == 1 else f"{base}?page={page}"
        try:
            html = requests.get(url, headers=HEADERS, timeout=30).text
        except Exception as e:
            print("EAI request error:", e, file=sys.stderr); break
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(".card, .col-md-4")
        if not cards: 
            break
        for c in cards:
            title_el = c.select_one("h5, h4, .card-title")
            title = normspace(title_el.get_text() if title_el else "")
            if not title: 
                continue
            link_el = c.select_one("a[href]")
            link = None
            if link_el and link_el.get("href"):
                href = link_el["href"]
                link = href if href.startswith("http") else f"https://www.eauctionsindia.com{href}"
            if link and link in seen_urls: 
                continue
            seen_urls.add(link or f"{url}#{len(out)}")
            text = c.get_text(" ", strip=True)

            rp = None
            m = re.search(r"Reserve\s*Price\s*:\s*₹?([\d,\.]+)", text, re.I)
            if m: rp = parse_money(m.group(1))

            adt = None
            m2 = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)", text, re.I)
            if m2: adt = parse_dt(m2.group(1))

            locality = detect_locality(title, text)
            typ = normalise_type(title)

            lat = lng = None
            if locality in GEO: lat, lng = GEO[locality]

            out.append({
                "id": sha1key("eai", title, link or url),
                "title": title or "Auction property",
                "type": typ,
                "address": None,
                "locality": locality or "Jaipur",
                "lat": lat, "lng": lng,
                "reserve_price": rp,
                "emd": None,
                "auction_date": adt,
                "bank": None,
                "source": link or url,
                "status": "Open",
                "source_portal": "eAuctionsIndia"
            })
        page += 1
    return out

# -------- SOURCE 2: Bank DRT (Jaipur) --------
def scrape_bankdrt():
    url = "https://www.bankdrt.com/nf/auction/show_auctions1.php?drt=Jaipur"
    out = []
    try:
        html = requests.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.select("table tr"):
            tds = [normspace(td.get_text()) for td in tr.select("td")]
            a = tr.select_one("a[href]")
            if not a or not tds: 
                continue
            link = a["href"]
            link = link if link.startswith("http") else f"https://www.bankdrt.com/nf/auction/{link}"
            title = tds[0] or "DRT Jaipur Auction"
            text = " ".join(tds)

            rp = None
            m = re.search(r"Reserve\s*Price\s*[:\-]?\s*₹?([\d,\.]+)", text, re.I)
            if m: rp = parse_money(m.group(1))
            adt = None
            m2 = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)", text)
            if m2: adt = parse_dt(m2.group(1))

            locality = detect_locality(title, text) or "Jaipur"
            typ = normalise_type(title)
            lat = lng = None
            if locality in GEO: lat, lng = GEO[locality]

            out.append({
                "id": sha1key("drt", title, link),
                "title": title,
                "type": typ,
                "address": None,
                "locality": locality,
                "lat": lat, "lng": lng,
                "reserve_price": rp,
                "emd": None,
                "auction_date": adt,
                "bank": None,
                "source": link,
                "status": "Open",
                "source_portal": "BankDRT"
            })
    except Exception as e:
        print("Bank DRT scrape error:", e, file=sys.stderr)
    return out

# -------- SOURCE 3: MSTC forthcoming (scan for Jaipur/Rajasthan) --------
def scrape_mstc():
    url = "https://www.mstcindia.co.in/contenthindi/Forthcoming_e_Auctions_For_All_regionshindi.aspx"
    out = []
    try:
        html = requests.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")
        for tr in soup.select("tr"):
            txt = normspace(tr.get_text(" "))
            if not txt: 
                continue
            if "jaipur" in txt.lower() or "rajasthan" in txt.lower():
                title = txt.split("\n")[0][:120] or "MSTC e-Auction (Rajasthan)"
                adt = None
                m2 = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)", txt, re.I)
                if m2: adt = parse_dt(m2.group(1))
                locality = detect_locality(txt) or "Jaipur"
                typ = normalise_type(txt)
                lat = lng = None
                if locality in GEO: lat, lng = GEO[locality]
                out.append({
                    "id": sha1key("mstc", title, txt),
                    "title": title,
                    "type": typ,
                    "address": None,
                    "locality": locality,
                    "lat": lat, "lng": lng,
                    "reserve_price": None,
                    "emd": None,
                    "auction_date": adt,
                    "bank": None,
                    "source": url,
                    "status": "Open",
                    "source_portal": "MSTC"
                })
    except Exception as e:
        print("MSTC scrape error:", e, file=sys.stderr)
    return out

# -------- Utilities --------
def dedup(rows):
    seen, out = set(), []
    for r in rows:
        key = r.get("id") or sha1key(r.get("title",""), r.get("auction_date",""), r.get("source",""))
        if key in seen: 
            continue
        seen.add(key)
        r["id"] = key
        out.append(r)
    return out

def keep_jaipur(rows):
    kept = []
    for r in rows:
        blob = " ".join([str(r.get("title","")), str(r.get("address","")), str(r.get("locality",""))]).lower()
        if "jaipur" in blob or r.get("locality") in COLONY_ALIASES.values() or r.get("locality") in GEO.keys():
            kept.append(r)
    return kept

def main():
    all_rows = []
    all_rows += scrape_eai()
    all_rows += scrape_bankdrt()
    all_rows += scrape_mstc()

    all_rows = keep_jaipur(all_rows)
    all_rows = dedup(all_rows)

    # add pins where we have coordinates
    for r in all_rows:
        if (not r.get("lat")) and r.get("locality") in GEO:
            r["lat"], r["lng"] = GEO[r["locality"]]

    Path("data").mkdir(parents=True, exist_ok=True)
    Path("data/listings.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2))
    print(f"Wrote {len(all_rows)} listings at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
