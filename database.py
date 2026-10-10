import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import (create_engine, MetaData, Table, Column, Integer, String,
                        Numeric, DateTime, Text, select, insert, update)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

STATUSES = ["Draft", "In progress", "Sent to customer", "Approved", "Completed", "Cancelled"]
metadata = MetaData()
users = Table("sg_users", metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(80), unique=True, nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("role", String(20), nullable=False))
quotes = Table("sg_quotations", metadata,
    Column("id", Integer, primary_key=True),
    Column("number", String(80), unique=True, nullable=False),
    Column("customer", String(200), nullable=False),
    Column("phone", String(30), nullable=False),
    Column("address", Text, nullable=False),
    Column("capacity", Numeric(10, 2), nullable=False),
    Column("amount", Numeric(14, 2), nullable=False),
    Column("status", String(30), nullable=False),
    Column("notes", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("updated_by", String(80), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False))
history = Table("sg_history", metadata,
    Column("id", Integer, primary_key=True),
    Column("quotation_id", Integer, nullable=False),
    Column("version", Integer, nullable=False),
    Column("actor", String(80), nullable=False),
    Column("timestamp", DateTime(timezone=True), nullable=False),
    Column("details", Text, nullable=False))

def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"{salt}:{digest}"

def password_matches(password, stored):
    salt, digest = stored.split(":")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return hmac.compare_digest(actual, digest)

class ConflictError(Exception):
    pass

class Store:
    def __init__(self, url):
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        options = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if url == "sqlite:///:memory:" else {}
        self.engine = create_engine(url, pool_pre_ping=True, **options)

    def initialize(self, username, password):
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            if conn.execute(select(users.c.id).limit(1)).first() is None:
                if not username or len(password) < 8:
                    raise ValueError("Set ADMIN_USERNAME and ADMIN_PASSWORD (at least 8 characters) to create the first administrator.")
                try:
                    with conn.begin_nested():
                        conn.execute(insert(users).values(username=username.lower().strip(), password_hash=password_hash(password), role="admin"))
                except IntegrityError:
                    pass

    def login(self, username, password):
        with self.engine.connect() as conn:
            row = conn.execute(select(users).where(users.c.username == username.lower().strip())).mappings().first()
        if row and password_matches(password, row["password_hash"]):
            return {"username": row["username"], "role": row["role"]}
        return None

    def add_user(self, username, password):
        username = username.lower().strip()
        if not 2 <= len(username) <= 5:
            raise ValueError("Username must contain 2–5 characters.")
        if len(password) < 8:
            raise ValueError("Password must contain at least 8 characters.")
        with self.engine.begin() as conn:
            conn.execute(insert(users).values(username=username, password_hash=password_hash(password), role="member"))

    def list_quotes(self):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(quotes).order_by(quotes.c.updated_at.desc())).mappings()]

    def get_quote(self, quote_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(quotes).where(quotes.c.id == quote_id)).mappings().first()
            return dict(row) if row else None

    def save(self, data, actor, quote_id=None, version=None):
        data = dict(data)
        for key in ("number", "customer", "phone", "address", "notes"):
            data[key] = data[key].strip()
        data["number"] = data["number"].upper()
        if not data["number"] or not data["customer"]:
            raise ValueError("Quotation number and customer name are required.")
        if len(data["number"]) > 80 or len(data["customer"]) > 200 or len(data["phone"]) > 30:
            raise ValueError("Quotation number, customer name, or phone is too long.")
        try:
            for key in ("capacity", "amount"):
                value = Decimal(str(data[key]))
                if not value.is_finite():
                    raise ValueError("Capacity and amount must be finite numbers.")
                data[key] = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError):
            raise ValueError("Enter valid capacity and amount values.") from None
        if data["capacity"] <= 0 or data["amount"] < 0 or data["status"] not in STATUSES:
            raise ValueError("Capacity must be positive, amount cannot be negative, and status must be valid.")
        if data["capacity"] > Decimal("99999999.99") or data["amount"] > Decimal("999999999999.99"):
            raise ValueError("Capacity or amount exceeds the allowed maximum.")
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            old = None
            if quote_id is None:
                new_version = 1
                quote_id = conn.execute(insert(quotes).values(**data, version=1, updated_by=actor, updated_at=now)).inserted_primary_key[0]
            else:
                old = conn.execute(select(quotes).where(quotes.c.id == quote_id)).mappings().first()
                new_version = version + 1
                result = conn.execute(update(quotes).where(quotes.c.id == quote_id, quotes.c.version == version).values(**data, version=new_version, updated_by=actor, updated_at=now))
                if result.rowcount != 1:
                    raise ConflictError("Another member has updated this quotation. Your changes were not saved. Reload the latest quotation and reapply your changes.")
            details = "Quotation created" if old is None else "\n".join(f"{key}: {old[key]} → {value}" for key, value in data.items() if str(old[key]) != str(value)) or "Saved without field changes"
            conn.execute(insert(history).values(quotation_id=quote_id, version=new_version, actor=actor, timestamp=now, details=details))
        return quote_id

    def get_history(self, quote_id):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(history).where(history.c.quotation_id == quote_id).order_by(history.c.version.desc())).mappings()]
