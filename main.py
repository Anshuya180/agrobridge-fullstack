import os, sqlite3, hashlib, hmac, base64, time, secrets
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import ml

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DB_PATH", os.path.join(ROOT, "agrobridge.db"))
SECRET = os.environ.get("SECRET", "dev-change-me").encode()
app = FastAPI(title="AgroBridge")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
def hp(pw, salt): return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000).hex()
def sign(b): return hmac.new(SECRET, b.encode(), "sha256").hexdigest()
def token(uid):
    b = f"{uid}.{int(time.time()) + 7 * 86400}"
    return base64.urlsafe_b64encode(f"{b}.{sign(b)}".encode()).decode()
def add_user(c, name, email, pw, role, country):
    salt = secrets.token_hex(8)
    return c.execute("insert into users(name,email,salt,pw,role,country) values(?,?,?,?,?,?)", (name, email, salt, hp(pw, salt), role, country)).lastrowid

with db() as c:
    c.executescript("""
    create table if not exists users(id integer primary key, name text, email text unique, salt text, pw text, role text, country text);
    create table if not exists listings(id integer primary key, farmer_id int, crop text, qty_t real, price real, location text, quality text, status text default 'open');
    create table if not exists offers(id integer primary key, listing_id int, buyer_id int, qty_t real, price real, status text default 'pending');""")
    if not c.execute("select 1 from users").fetchone():   # demo sellers so the marketplace isn't empty
        for i, (n, cr, q, pr, loc, note) in enumerate([("Ramesh Kumar", "mustard", 20, 6450, "Hisar, Haryana", "Moisture 7%, bold grain"),
                ("Gurdeep Singh", "wheat", 50, 2550, "Karnal, Haryana", "Sharbati, clean"), ("Savita Devi", "soybean", 15, 4900, "Ujjain, Madhya Pradesh", "Grade A")]):
            uid = add_user(c, n, f"demo{i}@example.com", secrets.token_hex(8), "farmer", "India")
            c.execute("insert into listings(farmer_id,crop,qty_t,price,location,quality) values(?,?,?,?,?,?)", (uid, cr, q, pr, loc, note))

def me(authorization: Optional[str] = Header(None)):
    try:
        uid, exp, sig = base64.urlsafe_b64decode(authorization.split()[1]).decode().split(".")
        if not hmac.compare_digest(sig, sign(f"{uid}.{exp}")) or int(exp) < time.time(): raise ValueError
        with db() as c: u = c.execute("select id,name,role,country from users where id=?", (uid,)).fetchone()
        if not u: raise ValueError
        return dict(u)
    except Exception:
        raise HTTPException(401, "Please log in")

class Reg(BaseModel):
    name: str; email: str; password: str; role: str; country: str = "India"
class Login(BaseModel):
    email: str; password: str
class NewListing(BaseModel):
    crop: str; qty: float; price: float; loc: str; note: str = ""
class NewOffer(BaseModel):
    lid: int; qty: float; price: float

@app.post("/api/register")
def register(r: Reg):
    if r.role not in ("farmer", "buyer"): raise HTTPException(400, "Role must be farmer or buyer")
    if len(r.password) < 6 or "@" not in r.email or not r.name.strip(): raise HTTPException(400, "Enter your name, a valid email and a password of 6+ characters")
    try:
        with db() as c: uid = add_user(c, r.name.strip(), r.email.strip().lower(), r.password, r.role, r.country)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "This email is already registered")
    return {"token": token(uid), "user": {"id": uid, "name": r.name.strip(), "role": r.role, "country": r.country}}

@app.post("/api/login")
def login(r: Login):
    with db() as c: u = c.execute("select * from users where email=?", (r.email.strip().lower(),)).fetchone()
    if not u or not hmac.compare_digest(u["pw"], hp(r.password, u["salt"])): raise HTTPException(401, "Wrong email or password")
    return {"token": token(u["id"]), "user": {"id": u["id"], "name": u["name"], "role": u["role"], "country": u["country"]}}

LQ = ("select l.id,l.farmer_id fid,l.crop,l.qty_t qty,l.price,l.location loc,l.quality note,l.status,u.name farmer "
      "from listings l join users u on u.id=l.farmer_id")

@app.get("/api/listings")
def listings(all: int = 0):
    with db() as c: return [dict(r) for r in c.execute(LQ + ("" if all else " where l.status='open'") + " order by l.id desc")]

@app.get("/api/listings/mine")
def my_listings(u=Depends(me)):
    with db() as c: return [dict(r) for r in c.execute(LQ + " where l.farmer_id=? order by l.id desc", (u["id"],))]

@app.post("/api/listings")
def add_listing(l: NewListing, u=Depends(me)):
    if u["role"] != "farmer": raise HTTPException(403, "Only farmers can sell")
    if l.crop not in ml.CROPS or l.qty <= 0 or l.price <= 0 or not l.loc.strip(): raise HTTPException(400, "Enter crop, quantity, price and location")
    with db() as c: c.execute("insert into listings(farmer_id,crop,qty_t,price,location,quality) values(?,?,?,?,?,?)", (u["id"], l.crop, l.qty, l.price, l.loc, l.note))
    return {"ok": True}

@app.get("/api/offers/mine")
def my_offers(u=Depends(me)):
    where = "l.farmer_id=?" if u["role"] == "farmer" else "o.buyer_id=?"
    with db() as c:
        return [dict(r) for r in c.execute("select o.id,o.listing_id lid,o.buyer_id bid,o.qty_t qty,o.price,o.status,b.name buyer,b.country bc from offers o "
                f"join listings l on l.id=o.listing_id join users b on b.id=o.buyer_id where {where} order by o.id desc", (u["id"],))]

@app.post("/api/offers")
def make_offer(o: NewOffer, u=Depends(me)):
    if u["role"] != "buyer": raise HTTPException(403, "Only buyers can make offers")
    with db() as c:
        l = c.execute("select * from listings where id=? and status='open'", (o.lid,)).fetchone()
        if not l: raise HTTPException(404, "Listing not available")
        if not (0 < o.qty <= l["qty_t"]) or o.price <= 0: raise HTTPException(400, f"Quantity must be up to {l['qty_t']} tonnes and price above 0")
        c.execute("insert into offers(listing_id,buyer_id,qty_t,price) values(?,?,?,?)", (o.lid, u["id"], o.qty, o.price))
    return {"ok": True}

@app.post("/api/offers/{oid}/accept")
def accept(oid: int, u=Depends(me)):
    with db() as c:
        o = c.execute("select o.listing_id, l.farmer_id from offers o join listings l on l.id=o.listing_id where o.id=?", (oid,)).fetchone()
        if not o or o["farmer_id"] != u["id"]: raise HTTPException(403, "Not your listing")
        c.execute("update offers set status=case when id=? then 'accepted' else 'rejected' end where listing_id=?", (oid, o["listing_id"]))
        c.execute("update listings set status='sold' where id=?", (o["listing_id"],))
    return {"ok": True}

@app.get("/api/forecast")
def forecast(crop: str = "mustard"):
    if crop not in ml.CROPS: raise HTTPException(404, "Unknown crop")
    return ml.forecast(crop)

@app.get("/health")
def health(): return {"ok": True}

app.mount("/", StaticFiles(directory=os.path.join(ROOT, "frontend"), html=True), name="frontend")
