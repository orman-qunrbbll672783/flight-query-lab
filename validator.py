"""Row validation: airport list loading, single-row checks, record building."""
import math
import re
from datetime import datetime

FIELD_NAMES = (
    "flight_id",
    "origin",
    "destination",
    "departure_datetime",
    "arrival_datetime",
    "price",
)
FIELD_COUNT = len(FIELD_NAMES)

DATETIME_FORMAT = "%Y-%m-%d %H:%M"

# [0-9] and [A-Z] are used on purpose instead of \d, \w, str.isalnum() or
# str.isupper(): those also accept non-ASCII characters such as "Ā" or "٣".
_FLIGHT_ID_RE = re.compile(r"[A-Za-z0-9]{2,8}")
_AIRPORT_RE = re.compile(r"[A-Z]{3}")
_DATETIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}")


def load_airports(path: str) -> set[str]:
    """Read an airport list file and return the set of codes.

    One code per line. Strip whitespace; skip blank lines and lines
    starting with '#'.
    """
    codes = set()
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            code = line.strip()
            if code and not code.startswith("#"):
                codes.add(code)
    return codes


def parse_datetime(value: str) -> datetime | None:
    """Return a datetime if value is exactly 'YYYY-MM-DD HH:MM' and real, else None.

    strptime alone is not enough: it accepts '2025-1-5 9:3', so the exact
    shape is checked with a regular expression first.
    """
    if not isinstance(value, str) or not _DATETIME_RE.fullmatch(value):
        return None
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except ValueError:
        return None


def is_valid_datetime(value: str) -> bool:
    """True if value is a real date and time written exactly as YYYY-MM-DD HH:MM."""
    return parse_datetime(value) is not None


def _is_valid_airport(code: str, airports: set[str]) -> bool:
    return bool(_AIRPORT_RE.fullmatch(code)) and code in airports


def validate_row(fields: list[str], airports: set[str]) -> str | None:
    """Check one CSV row (fields as returned by csv.reader, not yet stripped).

    Return None if the row is valid, otherwise the error code of the
    FIRST failing check (checks 1-11 in the specification, in order).
    Does not check for duplicates.
    """
    # 1. Exactly six fields.
    if len(fields) != FIELD_COUNT:
        return "WRONG_FIELD_COUNT"

    values = [str(field).strip() for field in fields]
    flight_id, origin, destination, departure, arrival, price_text = values

    # 2. No empty field.
    if any(value == "" for value in values):
        return "MISSING_FIELD"

    # 3. Flight id: 2-8 ASCII letters or digits.
    if not _FLIGHT_ID_RE.fullmatch(flight_id):
        return "INVALID_FLIGHT_ID"

    # 4.-5. Airports: three uppercase ASCII letters and in the airport list.
    if not _is_valid_airport(origin, airports):
        return "INVALID_ORIGIN"
    if not _is_valid_airport(destination, airports):
        return "INVALID_DESTINATION"

    # 6. Origin and destination must differ.
    if origin == destination:
        return "SAME_ORIGIN_DESTINATION"

    # 7.-8. Real date and time in the exact format.
    departure_dt = parse_datetime(departure)
    if departure_dt is None:
        return "INVALID_DEPARTURE"
    arrival_dt = parse_datetime(arrival)
    if arrival_dt is None:
        return "INVALID_ARRIVAL"

    # 9. Arrival strictly after departure.
    if arrival_dt <= departure_dt:
        return "ARRIVAL_NOT_AFTER_DEPARTURE"

    # 10. Price must convert with float() and be finite.
    try:
        price = float(price_text)
    except ValueError:
        return "INVALID_PRICE"
    if not math.isfinite(price):
        return "INVALID_PRICE"

    # 11. Price must be positive.
    if price <= 0:
        return "NON_POSITIVE_PRICE"

    return None


def to_record(fields: list[str]) -> dict:
    """Turn a valid row into a flight record dictionary.

    Keys: flight_id, origin, destination, departure_datetime,
    arrival_datetime (stripped strings) and price (float).
    """
    values = [str(field).strip() for field in fields]
    record = dict(zip(FIELD_NAMES[:-1], values[:-1]))
    record["price"] = float(values[-1])
    return record
