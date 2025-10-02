import re, hashlib, time, random
from datetime import datetime
from dateutil.parser import parse as dtparse

UA = "Mozilla/5.0 (compatible; JaipurAuctionBot/1.2; +https://github.com/you)"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.8"}

COLONY_ALIASES = {
    # west/south/central etc — extend freely
    "vaishali nagar":"Vaishali Nagar","queens road":"Queens Road","ajmer road":"Ajmer Road",
    "chitrakoot":"Chitrakoot","sodala":"Sodala","jhotwara":"Jhotwara","mansarovar":"Mansarovar",
    "new sanganer road":"New Sanganer Road","pratap nagar":"Pratap Nagar","sanganer":"Sanganer",
    "tonk road":"Tonk Road","sitapura":"Sitapura","jagatpura":"Jagatpura","malviya nagar":"Malviya Nagar",
    "c-scheme":"C-Scheme","c scheme":"C-Scheme","bapu nagar":"Bapu Nagar","ashok nagar":"Ashok Nagar",
    "mi road":"MI Road","bani park":"Bani Park","vidhyadhar nagar":"Vidhyadhar Nagar","vki":"VKI",
    "lal kothi":"Lal Kothi","jawahar nagar":"Jawahar Nagar","durgapura":"Durgapura","gopalpura":"Gopalpura",
    "amer":"Amer","raja park":"Raja Park","sikar road":"Sikar Road","delhi road":"Delhi Road","jln marg":"JLN Marg"
}
GEO = {
    "Vaishali Nagar": (26.914, 75.748), "Mansarovar": (26.858, 75.770), "Ajmer Road": (26.885, 75.730),
    "Queens Road": (26.908, 75.760), "C-Scheme": (26.912, 75.809), "Jagatpura": (26.822, 75.836),
    "Pratap Nagar": (26.788, 75.824), "Sodala": (26.898, 75.787), "Bani Park": (26.928, 75.797),
    "Jhotwara": (26.955, 75.740), "Vidhyadhar Nagar": (26.954, 75.784), "Tonk Road": (26.861, 75.802),
    "Malviya Nagar": (26.853, 75.815), "Amer": (26.985, 75.851), "Raja Park": (26.902, 75.829)
}

BANK_WORDS = [
    "SBI","State Bank of India","HDFC","ICICI","Axis","Punjab National Bank","PNB",
    "Bank of Baroda","Canara Bank","Union Bank","IDBI","Kotak","Indian Bank","UCO Bank",
    "Bank of India","Central Bank of India"
]

JUNK_PATTERNS = [
    r"welcome guest", r"please register", r"judgments?\b", r"rules\b.*regulations",
    r"information desk", r"gallery", r"services\b"
]

def norm(s): return re.sub(r"\s+"," ", (s or "")).strip()
def sha1key(*parts): return hashlib.sha1("|".join(norm(p).lower() for p in parts).encode()).hexdigest()

def parse_money(text):
    if not text: return None
    t = text.lower().replace(",", "").replace("₹","").replace("rs.","")
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    return int(float(m.group(1))) if m else None

def parse_dt(text):
    if not text: return None
    try: return dtparse(norm(text), dayfirst=True).strftime("%Y-%m-%d %H:%M")
    except: return None

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
    blob=" ".join(norm(x) for x in texts if x)
    for b in BANK_WORDS:
        import re as _re
        if _re.search(rf"\b{_re.escape(b)}\b", blob, _re.I): return b
    return None

def looks_junky(title):
    t=(title or "").lower()
    if len(t) < 10: return True
    import re as _re
    return any(_re.search(rx, t) for rx in JUNK_PATTERNS)

def polite_sleep():
    time.sleep(0.8 + random.random()*0.7)

def quality_filter(rows):
    out=[]
    for r in rows:
        if looks_junky(r.get("title")): continue
        blob=" ".join(str(r.get(k,"")) for k in ["title","address","locality"]).lower()
        if "jaipur" not in blob and not r.get("locality"): continue
        if not (r.get("reserve_price") or r.get("auction_date") or r.get("source")): continue
        out.append(r)
    return out

def backfill_geo(rows):
    for r in rows:
        loc=r.get("locality")
        if loc in GEO and (not r.get("lat")):
            r["lat"], r["lng"] = GEO[loc]
    return rows

def dedup(rows):
    seen=set(); out=[]
    for r in rows:
        key=r.get("id") or sha1key(r.get("title",""), r.get("auction_date",""), r.get("source",""))
        if key in seen: continue
        seen.add(key); r["id"]=key; out.append(r)
    return out
