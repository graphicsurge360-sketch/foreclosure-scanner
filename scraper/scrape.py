import re, json, hashlib, sys
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse as dtparse

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JaipurAuctionBot/1.1; +https://github.com/you)"}

# --- Heuristics / vocab ---
BANK_WORDS = [
    "SBI","State Bank of India","HDFC","ICICI","Axis","Punjab National Bank","PNB",
    "Bank of Baroda","BoB","Canara Bank","Union Bank","IDBI","Kotak","Indian Bank"
]

JUNK_TITLE_PATTERNS = [
    r"welcome guest",
    r"please register",
    r"on auction m&a options",
    r"judgments? legal",
    r"rules drt.*regulations",
    r"information desk",
]

# --- Jaipur colonies/areas (aliases + normalised) ---
COLONY_ALIASES = {
    "vaishali nagar":"Vaishali Nagar","vaishalinagar":"Vaishali Nagar",
    "queens road":"Queens Road","queen's road":"Queens Road",
    "ajmer road":"Ajmer Road","ajmer rd":"Ajmer Road",
    "chitrakoot":"Chitrakoot","niwaru road":"Niwaru Road","sodala":"Sodala","bais godam":"Bais Godam",
    "jhotwara":"Jhotwara","hathoj":"Hathoj","mansarovar":"Mansarovar","new sanganer road":"New Sanganer Road",
    "pratap nagar":"Pratap Nagar","pratab nagar":"Pratap Nagar","sanganer":"Sanganer","tonk road":"Tonk Road",
    "sitapura":"Sitapura","jagatpura":"Jagatpura","malviya nagar":"Malviya Nagar","c-scheme":"C-Scheme","c scheme":"C-Scheme",
    "bapu nagar":"Bapu Nagar","ashok nagar":"Ashok Nagar","mi road":"MI Road","bani park":"Bani Park","banipark":"Bani Park",
    "vidhyadhar nagar":"Vidhyadhar Nagar","vidyadhar nagar":"Vidhyadhar Nagar","vki":"VKI","lal kothi":"Lal Kothi",
    "jawahar nagar":"Jawahar Nagar","agrawal farm":"Agrawal Farm","durgapura":"Durgapura","gopalpura":"Gopalpura",
    "amer":"Amer","rajapark":"Raja Park","raja park":"Raja Park","sikar road":"Sikar Road","delhi road":"Delhi Road",
    "jln marg":"JLN Marg","jawaharlal nehru marg":"JLN Marg"
}

GEO = {
    "Vaishali Nagar": (26.914, 75.748), "Mansarovar": (26.858, 75.770), "Ajmer Road": (26.885, 75.730),
    "Queens Road": (26.908, 75.760), "C-Scheme": (26.912, 75.809), "Jagatpura": (26.822, 75.836),
    "Pratap Nagar": (26.788, 75.824), "Sodala": (26.898, 75.787), "Bani Park": (26.928, 75.797),
    "Jhotwara": (26.955, 75.740), "Vidhyadhar Nagar": (26.954, 75.784), "Tonk Road": (26.861, 75.802),
    "Malviya Nagar": (26.853, 75.815), "Amer": (26.985, 75.851)
}

def norm(s): return re.sub(r"\s+"," ",(s or "")).strip()
def sha1key(*parts): return hashlib.sha1("|".join(norm(p).lower() for p in parts).encode()).hexdigest()

def parse_money(text):
    if not text: return None
    t = text.replace(",","").replace("₹","").replace("rs.","").lower()
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return int(float(m.group(1))) if m else None

def parse_dt(text):
    if not text: return None
    try:
        return dtparse(norm(text), dayfirst=True).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None

def normalise_type(title):
    t=(title or "").lower()
    if any(k in t for k in ["flat","apartment"]): return "Flat"
    if "plot" in t: return "Plot"
    if any(k in t for k in ["villa","house","independent"]): return "House"
    if any(k in t for k in ["shop","showroom","office","commercial","industrial","warehouse","godown"]): return "Commercial"
    if "land" in t: return "Land"
    return "Property"

def detect_locality(*texts):
    blob=(" ".join(norm(x) for x in texts if x)).lower()
    for alias, proper in COLONY_ALIASES.items():
        if alias in blob: return proper
    if "jaipur" in blob: return "Jaipur"
    return None

def detect_bank(*texts):
    blob=(" ".join(norm(x) for x in texts if x))
    for b in BANK_WORDS:
        if re.search(rf"\b{re.escape(b)}\b", blob, re.I): return b
    return None

def looks_junky(title_text):
    t=(title_text or "").lower()
    if len(t) < 12: return True
    for rx in JUNK_TITLE_PATTERNS:
        if re.search(rx, t): return True
    return False

# ---------- SOURCE 1: eAuctionsIndia (Jaipur pages) ----------
def scrape_eai():
    base="https://www.eauctionsindia.com/city/jaipur"
    out, page, seen=set(),1,set()
    rows=[]
    while page<=4:
        url = base if page==1 else f"{base}?page={page}"
        try:
            html=requests.get(url,headers=HEADERS,timeout=30).text
        except Exception as e:
            print("EAI request error:", e, file=sys.stderr); break
        soup=BeautifulSoup(html,"html.parser")
        cards = soup.select(".card, .col-md-4")
        if not cards: break
        for c in cards:
            title_el=c.select_one("h5,h4,.card-title")
            title=norm(title_el.get_text() if title_el else "")
            if looks_junky(title): continue
            text=c.get_text(" ",strip=True)
            link_el=c.select_one("a[href]")
            link=None
            if link_el and link_el.get("href"):
                href=link_el["href"]
                link=href if href.startswith("http") else f"https://www.eauctionsindia.com{href}"
            if link and link in seen: continue
            if link: seen.add(link)

            rp=None
            m=re.search(r"Reserve\s*Price\s*:\s*₹?([\d,\.]+)", text, re.I)
            if m: rp=parse_money(m.group(1))

            adt=None
            m2=re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)", text)
            if m2: adt=parse_dt(m2.group(1))

            locality=detect_locality(title,text)
            bank=detect_bank(title,text)
            typ=normalise_type(title)
            lat=lng=None
            if locality in GEO: lat,lng=GEO[locality]

            rows.append({
                "id": sha1key("eai", title, link or url),
                "title": title, "type": typ, "address": None,
                "locality": locality or "Jaipur", "lat": lat, "lng": lng,
                "reserve_price": rp, "emd": None, "auction_date": adt,
                "bank": bank, "source": link or url, "status": "Open",
                "source_portal": "eAuctionsIndia"
            })
        page += 1
    return rows

# ---------- SOURCE 2: BankDRT (Jaipur) ----------
def scrape_bankdrt():
    url="https://www.bankdrt.com/nf/auction/show_auctions1.php?drt=Jaipur"
    out=[]
    try:
        html=requests.get(url,headers=HEADERS,timeout=30).text
        soup=BeautifulSoup(html,"html.parser")
        for tr in soup.select("table tr"):
            tds=[norm(td.get_text()) for td in tr.select("td")]
            a=tr.select_one("a[href]")
            if not a or not tds: continue
            link=a["href"]; link=link if link.startswith("http") else f"https://www.bankdrt.com/nf/auction/{link}"
            title=tds[0] or "DRT Jaipur Auction"
            if looks_junky(title): continue
            text=" ".join(tds)

            rp=None
            m=re.search(r"Reserve\s*Price\s*[:\-]?\s*₹?([\d,\.]+)", text, re.I)
            if m: rp=parse_money(m.group(1))

            adt=None
            m2=re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)", text)
            if m2: adt=parse_dt(m2.group(1))

            locality=detect_locality(title,text) or "Jaipur"
            bank=detect_bank(title,text)
            typ=normalise_type(title)
            lat=lng=None
            if locality in GEO: lat,lng=GEO[locality]

            out.append({
                "id": sha1key("drt", title, link),
                "title": title, "type": typ, "address": None,
                "locality": locality, "lat": lat, "lng": lng,
                "reserve_price": rp, "emd": None, "auction_date": adt,
                "bank": bank, "source": link, "status": "Open",
                "source_portal": "BankDRT"
            })
    except Exception as e:
        print("BankDRT error:", e, file=sys.stderr)
    return out

# ---------- SOURCE 3: MSTC forthcoming (filter aggressively) ----------
def scrape_mstc():
    url="https://www.mstcindia.co.in/contenthindi/Forthcoming_e_Auctions_For_All_regionshindi.aspx"
    out=[]
    try:
        html=requests.get(url,headers=HEADERS,timeout=30).text
        soup=BeautifulSoup(html,"html.parser")
        for tr in soup.select("tr"):
            txt=norm(tr.get_text(" "))
            low=txt.lower()
            if not txt: continue
            if "jaipur" not in low and "rajasthan" not in low: continue
            if looks_junky(txt): continue

            title=txt[:140]
            adt=None
            m2=re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?)", txt)
            if m2: adt=parse_dt(m2.group(1))
            locality=detect_locality(txt) or "Jaipur"
            bank=detect_bank(txt)
            typ=normalise_type(txt)
            lat=lng=None
            if locality in GEO: lat,lng=GEO[locality]

            out.append({
                "id": sha1key("mstc", title, txt),
                "title": title, "type": typ, "address": None,
                "locality": locality, "lat": lat, "lng": lng,
                "reserve_price": None, "emd": None, "auction_date": adt,
                "bank": bank, "source": url, "status": "Open",
                "source_portal": "MSTC"
            })
    except Exception as e:
        print("MSTC error:", e, file=sys.stderr)
    return out

def dedup(rows):
    seen=set(); out=[]
    for r in rows:
        key=r.get("id") or sha1key(r.get("title",""), r.get("auction_date",""), r.get("source",""))
        if key in seen: continue
        seen.add(key); r["id"]=key; out.append(r)
    return out

def quality_filter(rows):
    good=[]
    for r in rows:
        title=(r.get("title") or "")
        if looks_junky(title): continue
        blob=" ".join(str(r.get(k,"")) for k in ["title","address","locality"]).lower()
        if "jaipur" not in blob and not r.get("locality"): continue
        # keep only if has at least a price OR a date (avoid totally empty rows)
        if not (r.get("reserve_price") or r.get("auction_date")): continue
        good.append(r)
    return good

def backfill_geo(rows):
    for r in rows:
        loc=r.get("locality")
        if loc in GEO and (not r.get("lat")):
            r["lat"], r["lng"]=GEO[loc]
    return rows

def main():
    all_rows=[]
    all_rows += scrape_eai()
    all_rows += scrape_bankdrt()
    all_rows += scrape_mstc()

    all_rows = quality_filter(all_rows)
    all_rows = dedup(all_rows)
    all_rows = backfill_geo(all_rows)

    Path("data").mkdir(parents=True, exist_ok=True)
    Path("data/listings.json").write_text(json.dumps(all_rows, ensure_ascii=False, indent=2))
    print(f"Wrote {len(all_rows)} high-quality listings at {datetime.now().isoformat()}")

if __name__=="__main__":
    main()
