import re, json, hashlib, sys
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as dtparse

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JaipurAuctionBot/1.0; +https://github.com/you)"}

def normspace(s): 
    import re
    return re.sub(r"\s+", " ", s or "").strip()

def sha1key(*parts):
    raw = "|".join(normspace(p).lower() for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def as_money(s):
    s = s.replace(",", "").replace("₹", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return int(float(m.group(1))) if m else None

def as_datetime_guess(s):
    s = normspace(s)
    try:
        return dtparse(s, dayfirst=True).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None

# ---------- SOURCE 1: eAuctionsIndia Jaipur ----------
def scrape_eauctionsindia_jaipur():
    url = "https://www.eauctionsindia.com/city/jaipur"
    out = []
    try:
        html = requests.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("div.col-md-4") or soup.select("div.card")
        for card in cards:
            title_el = card.select_one("h5,h4")
            title = normspace(title_el.get_text()) if title_el else None
            if not title: 
                continue
            text = card.get_text(" ", strip=True)
            rp = None
            m = re.search(r"Reserve Price\s*:\s*₹?([\d,\.]+)", text, re.I)
            if m: rp = as_money(m.group(1))
            adt = None
            m2 = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)", text, re.I)
            if m2: adt = as_datetime_guess(m2.group(1))

            link = None
            a = card.select_one("a[href*='immovable'], a[href*='auction'], a[href]")
            if a and a.get('href'):
                href = a['href']
                link = href if href.startswith('http') else f"https://www.eauctionsindia.com{href}"

            loc = None
            for guess in ["Vaishali Nagar","Mansarovar","Ajmer Road","Queens Road","C-Scheme","Hathoj","Kalyanpuri","Jagatpura","Pratap Nagar","Sodala","Jhotwara"]:
                if guess.lower() in title.lower():
                    loc = guess; break

            out.append({
                "id": sha1key("eai", title, link or ""),
                "title": title,
                "type": "Property",
                "address": None,
                "locality": loc or "Jaipur",
                "lat": None, "lng": None,
                "reserve_price": rp,
                "emd": None,
                "auction_date": adt,
                "bank": None,
                "source": link or url,
                "status": "Open",
                "source_portal": "eAuctionsIndia"
            })
    except Exception as e:
        print("eAuctionsIndia scrape error:", e, file=sys.stderr)
    return out

# ---------- SOURCE 2: Bank DRT Jaipur ----------
def scrape_bankdrt_jaipur():
    url = "https://www.bankdrt.com/nf/auction/show_auctions1.php?drt=Jaipur"
    out = []
    try:
        html = requests.get(url, headers=HEADERS, timeout=30).text
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table tr")
        for tr in rows:
            tds = [normspace(td.get_text()) for td in tr.select("td")]
            a = tr.select_one("a[href]")
            if len(tds) < 2 or not a: 
                continue
            title = tds[0] or "Auction asset (DRT Jaipur)"
            link = a["href"]
            link = link if link.startswith("http") else f"https://www.bankdrt.com/nf/auction/{link}"
            text = " ".join(tds)
            rp = None
            m = re.search(r"Reserve\s*Price\s*[:\-]?\s*₹?([\d,\.]+)", text, re.I)
            if m: rp = as_money(m.group(1))
            adt = None
            m2 = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})", text)
            if m2: adt = as_datetime_guess(m2.group(1))

            out.append({
                "id": sha1key("drt", title, link),
                "title": title,
                "type": "Property",
                "address": None,
                "locality": "Jaipur",
                "lat": None, "lng": None,
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

# ---------- SOURCE 3: MSTC forthcoming (Rajasthan/Jaipur mentions) ----------
def scrape_mstc_forthcoming():
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
                tds = [normspace(td.get_text()) for td in tr.select("td")]
                if len(tds) < 1: 
                    continue
                title = tds[0] or "MSTC e-Auction (Rajasthan)"
                date_guess = None
                m2 = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\s*\d{0,2}:?\d{0,2}\s*(?:AM|PM)?)", txt, re.I)
                if m2: date_guess = as_datetime_guess(m2.group(1))
                out.append({
                    "id": sha1key("mstc", title, txt),
                    "title": title,
                    "type": "Property",
                    "address": None,
                    "locality": "Jaipur",
                    "lat": None, "lng": None,
                    "reserve_price": None,
                    "emd": None,
                    "auction_date": date_guess,
                    "bank": None,
                    "source": url,
                    "status": "Open",
                    "source_portal": "MSTC"
                })
    except Exception as e:
        print("MSTC scrape error:", e, file=sys.stderr)
    return out

def dedup(rows):
    seen=set(); out=[]
    for r in rows:
        key = r.get("id") or sha1key(r.get("title",""), r.get("auction_date",""), r.get("source",""))
        if key in seen: continue
        seen.add(key)
        r["id"] = key
        out.append(r)
    return out

def is_jaipurish(text):
    if not text: return False
    t = text.lower()
    return any(k in t for k in ["jaipur","vaishali","mansarovar","ajmer road","queens road","c-scheme","jagatpura","jhotwara","sodala","pratap nagar","tonk road"])

def main():
    all_rows = []
    all_rows += scrape_eauctionsindia_jaipur()
    all_rows += scrape_bankdrt_jaipur()
    all_rows += scrape_mstc_forthcoming()

    # Keep Jaipur-ish only
    out = []
    for r in all_rows:
        blob = " ".join([str(r.get("title","")), str(r.get("address","")), str(r.get("locality",""))])
        if is_jaipurish(blob):
            out.append(r)

    out = dedup(out)

    Path("data").mkdir(parents=True, exist_ok=True)
    Path("data/listings.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Wrote {len(out)} listings at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
