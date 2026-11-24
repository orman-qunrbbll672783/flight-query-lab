"""Running queries against the flight database."""
from validator import FIELD_NAMES, is_valid_datetime

INVALID_QUERY = "INVALID_QUERY"

STRING_KEYS = ("flight_id", "origin", "destination")
DATETIME_KEYS = ("departure_datetime", "arrival_datetime")
NUMBER_KEYS = ("price", "min_price")
ALLOWED_KEYS = set(STRING_KEYS) | set(DATETIME_KEYS) | set(NUMBER_KEYS) | {
    "sort_by",
    "order",
    "limit",
}


def _is_number(value) -> bool:
    # bool is a subclass of int in Python, but booleans are not numbers here.
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_valid_query(query) -> bool:
    """True if the query only uses allowed keys with values of the right type."""
    if not isinstance(query, dict):
        return False
    for key, value in query.items():
        if key not in ALLOWED_KEYS:
            return False
        if key in STRING_KEYS and not isinstance(value, str):
            return False
        if key in DATETIME_KEYS and not is_valid_datetime(value):
            return False
        if key in NUMBER_KEYS and not _is_number(value):
            return False
        if key == "sort_by" and value not in FIELD_NAMES:
            return False
        if key == "order" and value not in ("asc", "desc"):
            return False
        if key == "limit" and not (_is_int(value) and value >= 0):
            return False
    if "order" in query and "sort_by" not in query:
        return False
    return True


def matches(flight: dict, query: dict) -> bool:
    """True if the flight passes every condition in the query (AND)."""
    for key in STRING_KEYS:
        if key in query and flight.get(key) != query[key]:
            return False
    # Datetimes are in the fixed zero-padded format, so comparing the
    # strings gives the same result as comparing the times.
    if "departure_datetime" in query:
        if not flight.get("departure_datetime", "") >= query["departure_datetime"]:
            return False
    if "arrival_datetime" in query:
        if not flight.get("arrival_datetime", "￿") <= query["arrival_datetime"]:
            return False
    if "price" in query and not flight["price"] <= query["price"]:
        return False
    if "min_price" in query and not flight["price"] >= query["min_price"]:
        return False
    return True


def run_query(db: list[dict], query: dict) -> dict:
    """Return one response entry for one query object.

    Valid query:   {"query": query, "matches": [...]}
    Invalid query: {"query": query, "error": "INVALID_QUERY", "matches": []}
    """
    if not is_valid_query(query):
        return {"query": query, "error": INVALID_QUERY, "matches": []}

    found = [flight for flight in db if matches(flight, query)]

    if "sort_by" in query:
        # sorted() is stable, also with reverse=True, so equal values keep
        # database order in both directions.
        found = sorted(
            found,
            key=lambda flight: flight[query["sort_by"]],
            reverse=query.get("order", "asc") == "desc",
        )

    if "limit" in query:
        found = found[: query["limit"]]

    return {"query": query, "matches": found}


def run_queries(db: list[dict], queries: dict | list) -> list[dict]:
    """Accept one query object or a list of them; always return a list."""
    if isinstance(queries, list):
        return [run_query(db, query) for query in queries]
    return [run_query(db, queries)]
