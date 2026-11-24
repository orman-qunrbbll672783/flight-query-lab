"""Reading CSV files into flight records and error messages."""
import csv
import os

from validator import to_record, validate_row


def read_lines(path: str) -> list[str]:
    """Return the physical lines of a UTF-8 file without their line endings.

    Handles both '\\n' and '\\r\\n' endings. Line i of the file is element
    i - 1 of the list, so line numbers stay exact.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        text = f.read()
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # the file ended with a newline
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def split_line(line: str) -> list[str]:
    """Split one CSV line into fields with the csv module."""
    try:
        return next(csv.reader([line]), [])
    except csv.Error:
        # Malformed line the csv module refuses; it is still checked.
        return line.split(",")


def _free_text(line: str) -> str:
    """The original line, kept on one log line."""
    return " ".join(line.splitlines())


def parse_files(paths: list[str], airports: set[str]) -> tuple[list[dict], list[str]]:
    """Process the CSV files in the order given.

    Return (records, errors):
      records - valid flight records, in input order
      errors  - one message per invalid row, in input order, formatted as
                "<file name>:<line number>: <ERROR_CODE> | <free text>"
                (base file name only, no timestamp or level, no newline)

    Also performs the DUPLICATE_FLIGHT check across all the files.
    Does not write any files and does not log anything itself.
    """
    records: list[dict] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()  # (flight_id, departure_datetime)

    for path in paths:
        name = os.path.basename(path)
        for line_number, line in enumerate(read_lines(path), start=1):
            if line_number == 1:
                continue  # header
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue  # blank or comment line

            fields = split_line(line)
            code = validate_row(fields, airports)
            if code is None:
                record = to_record(fields)
                key = (record["flight_id"], record["departure_datetime"])
                if key in seen:
                    code = "DUPLICATE_FLIGHT"
                else:
                    seen.add(key)
                    records.append(record)

            if code is not None:
                errors.append(f"{name}:{line_number}: {code} | {_free_text(line)}")

    return records, errors
