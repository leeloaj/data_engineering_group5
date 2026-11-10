import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pycountry
from dotenv import load_dotenv


REGION_ALIASES = {
    "bolivia": "BO",
    "czech republic": "CZ",
    "iran": "IR",
    "ivory coast": "CI",
    "kosovo": "XK",
    "moldova": "MD",
    "russia": "RU",
    "south korea": "KR",
    "taiwan": "TW",
    "tanzania": "TZ",
    "turkey": "TR",
    "united states of america": "US",
    "venezuela": "VE",
    "vietnam": "VN",
}


def spotify_track_id(value):
    """Normalize a bare Spotify track ID, Spotify URI, or open.spotify.com URL."""
    candidate = value.strip()
    if candidate.startswith("spotify:track:"):
        candidate = candidate.removeprefix("spotify:track:")
    elif candidate.startswith(("https://", "http://")):
        url = urlsplit(candidate)
        match = re.fullmatch(r"/(?:intl-[a-zA-Z-]+/)?track/([a-zA-Z0-9]+)/?", url.path)
        if url.netloc.lower() == "open.spotify.com" and match:
            candidate = match[1]
    if not re.fullmatch(r"[a-zA-Z0-9]{22}", candidate):
        raise ValueError(f"invalid Spotify track ID, URI, or URL: {value!r}")
    return candidate


def input_date(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(f"expected YYYY-MM-DD, got {value!r}")
    return date.fromisoformat(value)


def region_code(value):
    region = value.strip().casefold()
    if region == "global":
        return "GLOBAL"
    if region in REGION_ALIASES:
        return REGION_ALIASES[region]
    if region == "xk":
        return "XK"
    try:
        return pycountry.countries.lookup(region).alpha_2
    except LookupError:
        raise ValueError(f"unknown chart region: {value!r}") from None


def open_bronze():
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise ValueError("Set DATABASE_URL in the environment or .env")
    return psycopg.connect(dsn, autocommit=True)


def ensure_bronze(connection):
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(hashtext('group5_bronze_schema'))")
        schema_path = Path(__file__).resolve().parents[1] / "sql" / "bronze.sql"
        ddl = schema_path.read_text(encoding="utf-8")
        connection.execute(ddl, prepare=False)
