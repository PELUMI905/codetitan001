"""CodeTitan Travel API: FastAPI + SQLite."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "codetitan_travel.db")))
SECRET_KEY = os.getenv("CODETITAN_SECRET_KEY", "change-this-development-secret-before-deployment")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "24"))

app = FastAPI(title="CodeTitan Travel API", version="1.0.0", description="API for the CodeTitan Travel website")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@contextmanager
def get_db():
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS destinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country TEXT NOT NULL,
            description TEXT NOT NULL,
            price INTEGER NOT NULL CHECK(price >= 0),
            image TEXT NOT NULL DEFAULT '/images/category-1.jpg',
            featured INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            destination_id INTEGER NOT NULL REFERENCES destinations(id),
            travel_date TEXT NOT NULL,
            travelers INTEGER NOT NULL CHECK(travelers BETWEEN 1 AND 20),
            notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            country TEXT NOT NULL,
            phone TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        """)
        count = db.execute("SELECT COUNT(*) AS n FROM destinations").fetchone()["n"]
        if count == 0:
            now = datetime.now(timezone.utc).isoformat()
            starter_destinations = [
                ("Obudu Mountain Resort", "Nigeria", "A scenic mountain escape in Cross River State with cool weather and beautiful landscapes.", 185000, "/images/category-1.jpg", 1, 1, now),
                ("Zanzibar Beach Escape", "Tanzania", "Relax on turquoise water, white-sand beaches, and explore Stone Town's rich culture.", 520000, "/images/category-2.jpg", 1, 1, now),
                ("Paris City Break", "France", "Discover iconic landmarks, cafes, museums, and memorable walks through the city.", 890000, "/images/category-3.jpg", 1, 1, now),
                ("Cape Town Adventure", "South Africa", "Enjoy Table Mountain, ocean views, local food, and scenic coastal drives.", 610000, "/images/category-4.jpg", 1, 1, now),
                ("Dubai Discovery", "United Arab Emirates", "Experience modern attractions, desert excursions, shopping, and waterfront dining.", 740000, "/images/product-1.jpg", 0, 1, now),
                ("London Highlights", "United Kingdom", "Explore famous museums, historic streets, parks, and riverside landmarks.", 795000, "/images/product-2.jpg", 0, 1, now),
            ]
            db.executemany("""INSERT INTO destinations
                (name,country,description,price,image,featured,active,created_at) VALUES (?,?,?,?,?,?,?,?)""", starter_destinations)
        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        if admin_email and admin_password:
            if len(admin_password) < 12:
                raise RuntimeError("ADMIN_PASSWORD must be at least 12 characters long")
            user = db.execute("SELECT id FROM users WHERE email = ?", (admin_email,)).fetchone()
            if not user:
                db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)", (
                    os.getenv("ADMIN_NAME", "CodeTitan Admin"), admin_email, hash_password(admin_password), "admin", datetime.now(timezone.utc).isoformat()
                ))
            else:
                db.execute("UPDATE users SET role='admin' WHERE email=?", (admin_email,))


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return f"pbkdf2_sha256${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(derived).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_text, digest_text = encoded.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode())
        expected = base64.urlsafe_b64decode(digest_text.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def create_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    header = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = b64url(json.dumps({"sub": str(user_id), "role": role, "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=TOKEN_HOURS)).timestamp())}, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}"
    signature = hmac.new(SECRET_KEY.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{b64url(signature)}"


def decode_token(token: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = b64url(hmac.new(SECRET_KEY.encode(), unsigned.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("signature")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(claims.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        return claims
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Your session is invalid or has expired. Please sign in again.") from exc


def public_user(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "name": row["name"], "email": row["email"], "role": row["role"]}


def current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Please sign in to continue.")
    claims = decode_token(authorization.split(" ", 1)[1].strip())
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id=?", (int(claims["sub"]),)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Account not found. Please sign in again.")
    return public_user(row)


def admin_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Administrator access is required.")
    return user


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)

    def validate_fields(self):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.email.strip()):
            raise HTTPException(status_code=422, detail="Enter a valid email address.")


class LoginInput(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)


class BookingInput(BaseModel):
    destination_id: int
    travel_date: date
    travelers: int = Field(ge=1, le=20)
    notes: str = Field(default="", max_length=500)


class NewsletterInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=254)
    country: str = Field(min_length=2, max_length=80)
    phone: str = Field(default="", max_length=30)


class DestinationInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    country: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=10, max_length=1000)
    price: int = Field(ge=0, le=100_000_000)
    image: str = Field(default="/images/category-1.jpg", max_length=300)
    featured: bool = False
    active: bool = True


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/")
def root():
    return {"message": "Welcome to CodeTitan Travel API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health():
    with get_db() as db:
        db.execute("SELECT 1")
    return {"status": "ok", "database": "connected", "app": "CodeTitan Travel"}


@app.get("/api/destinations")
def list_destinations(q: str = Query(default="", max_length=100), include_inactive: bool = False):
    sql = "SELECT id,name,country,description,price,image,featured FROM destinations WHERE active=1"
    params: list = []
    if q.strip():
        term = f"%{q.strip()}%"
        sql += " AND (name LIKE ? OR country LIKE ? OR description LIKE ?)"
        params.extend([term, term, term])
    sql += " ORDER BY featured DESC, name COLLATE NOCASE"
    with get_db() as db:
        rows = db.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


@app.post("/api/auth/register", status_code=201)
def register(payload: RegisterInput):
    payload.validate_fields()
    name, email = payload.name.strip(), payload.email.strip().lower()
    with get_db() as db:
        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(status_code=409, detail="An account with this email already exists. Please sign in.")
        cursor = db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)", (
            name, email, hash_password(payload.password), "user", datetime.now(timezone.utc).isoformat()
        ))
        row = db.execute("SELECT * FROM users WHERE id=?", (cursor.lastrowid,)).fetchone()
    user = public_user(row)
    return {"access_token": create_token(user["id"], user["role"]), "token_type": "bearer", "user": user}


@app.post("/api/auth/login")
def login(payload: LoginInput):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (payload.email.strip().lower(),)).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    user = public_user(row)
    return {"access_token": create_token(user["id"], user["role"]), "token_type": "bearer", "user": user}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)):
    return user


@app.post("/api/bookings", status_code=201)
def create_booking(payload: BookingInput, user: dict = Depends(current_user)):
    if payload.travel_date < date.today():
        raise HTTPException(status_code=422, detail="Travel date cannot be in the past.")
    with get_db() as db:
        destination = db.execute("SELECT id FROM destinations WHERE id=? AND active=1", (payload.destination_id,)).fetchone()
        if not destination:
            raise HTTPException(status_code=404, detail="Destination not found or no longer available.")
        cursor = db.execute("INSERT INTO bookings(user_id,destination_id,travel_date,travelers,notes,status,created_at) VALUES(?,?,?,?,?,?,?)", (
            user["id"], payload.destination_id, payload.travel_date.isoformat(), payload.travelers,
            payload.notes.strip(), "pending", datetime.now(timezone.utc).isoformat()
        ))
        row = db.execute("""SELECT b.id,b.travel_date,b.travelers,b.notes,b.status,b.created_at,
            d.name AS destination,d.country,d.price FROM bookings b JOIN destinations d ON d.id=b.destination_id WHERE b.id=?""", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.get("/api/bookings/me")
def my_bookings(user: dict = Depends(current_user)):
    with get_db() as db:
        rows = db.execute("""SELECT b.id,b.travel_date,b.travelers,b.notes,b.status,b.created_at,
            d.name AS destination,d.country,d.price FROM bookings b JOIN destinations d ON d.id=b.destination_id
            WHERE b.user_id=? ORDER BY b.created_at DESC""", (user["id"],)).fetchall()
    return [dict(row) for row in rows]


@app.patch("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, user: dict = Depends(current_user)):
    with get_db() as db:
        row = db.execute("SELECT id,status FROM bookings WHERE id=? AND user_id=?", (booking_id, user["id"])).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Booking not found.")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Only pending booking requests can be cancelled.")
        db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
    return {"message": "Booking request cancelled.", "id": booking_id, "status": "cancelled"}


@app.post("/api/newsletter", status_code=201)
def subscribe(payload: NewsletterInput):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    with get_db() as db:
        existing = db.execute("SELECT id FROM subscribers WHERE email=?", (email,)).fetchone()
        if existing:
            return {"message": "You're already subscribed. Thanks for staying with CodeTitan!"}
        db.execute("INSERT INTO subscribers(name,email,country,phone,created_at) VALUES(?,?,?,?,?)", (
            payload.name.strip(), email, payload.country.strip(), payload.phone.strip(), datetime.now(timezone.utc).isoformat()
        ))
    return {"message": "Thanks for subscribing to CodeTitan Travel!"}


@app.get("/api/admin/bookings")
def admin_list_bookings(_: dict = Depends(admin_user)):
    with get_db() as db:
        rows = db.execute("""SELECT b.id,b.travel_date,b.travelers,b.notes,b.status,b.created_at,
            u.name AS customer_name,u.email AS customer_email,d.name AS destination,d.country,d.price
            FROM bookings b JOIN users u ON u.id=b.user_id JOIN destinations d ON d.id=b.destination_id
            ORDER BY b.created_at DESC""").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/admin/destinations", status_code=201)
def admin_create_destination(payload: DestinationInput, _: dict = Depends(admin_user)):
    with get_db() as db:
        cursor = db.execute("INSERT INTO destinations(name,country,description,price,image,featured,active,created_at) VALUES(?,?,?,?,?,?,?,?)", (
            payload.name.strip(), payload.country.strip(), payload.description.strip(), payload.price, payload.image,
            int(payload.featured), int(payload.active), datetime.now(timezone.utc).isoformat()
        ))
        row = db.execute("SELECT id,name,country,description,price,image,featured,active FROM destinations WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@app.put("/api/admin/destinations/{destination_id}")
def admin_update_destination(destination_id: int, payload: DestinationInput, _: dict = Depends(admin_user)):
    with get_db() as db:
        exists = db.execute("SELECT id FROM destinations WHERE id=?", (destination_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Destination not found.")
        db.execute("UPDATE destinations SET name=?,country=?,description=?,price=?,image=?,featured=?,active=? WHERE id=?", (
            payload.name.strip(), payload.country.strip(), payload.description.strip(), payload.price, payload.image,
            int(payload.featured), int(payload.active), destination_id
        ))
        row = db.execute("SELECT id,name,country,description,price,image,featured,active FROM destinations WHERE id=?", (destination_id,)).fetchone()
    return dict(row)


@app.delete("/api/admin/destinations/{destination_id}")
def admin_delete_destination(destination_id: int, _: dict = Depends(admin_user)):
    with get_db() as db:
        exists = db.execute("SELECT id FROM destinations WHERE id=?", (destination_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Destination not found.")
        # Soft delete preserves past booking history.
        db.execute("UPDATE destinations SET active=0 WHERE id=?", (destination_id,))
    return {"message": "Destination hidden from the public website."}
