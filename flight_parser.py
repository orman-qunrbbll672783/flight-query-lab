"""Flight Schedule Parser and Query Tool - command-line entry point.

Run from the project folder, for example:
    python flight_parser.py -i data/db.csv -a data/airports.txt
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime

from csv_loader import parse_files
from query import run_queries
from validator import load_airports

STUDENT_ID = "251ADB255"
FIRST_NAME = "Orman"
LAST_NAME = "Gurbanli"

LOGGER_NAME = "flight_parser"


class RuntimeProblem(Exception):
    """An expected problem that ends the run with exit code 1."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flight_parser.py",
        description="Validate flight schedule CSV files, store valid flights "
        "as a JSON database and run queries against it.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-i", metavar="FILE", help="parse a single CSV file")
    source.add_argument("-d", metavar="FOLDER", help="parse every .csv file in a folder")
    source.add_argument("-j", metavar="FILE", help="load an existing JSON database")
    parser.add_argument("-a", metavar="FILE", help="airport list (required with -i and -d)")
    parser.add_argument("-o", metavar="FILE", help="output JSON database (default: db.json)")
    parser.add_argument("-q", metavar="FILE", help="JSON file with queries to run")
    parser.add_argument("-r", metavar="FOLDER", help="folder for the response file (default: .)")
    return parser


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse and check the arguments. argparse exits with code 2 on usage errors."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.j is None and args.a is None:
        parser.error("-a is required with -i and -d")
    if args.j is not None and args.o is not None:
        parser.error("-o can only be used with -i or -d")
    return args


def csv_paths_in_folder(folder: str) -> list[str]:
    """Every file in the folder (not sub-folders) ending in .csv, sorted by name."""
    if not os.path.isdir(folder):
        raise RuntimeProblem(f"folder not found: {folder}")
    try:
        names = os.listdir(folder)
    except OSError as exc:
        raise RuntimeProblem(f"cannot read folder {folder}: {exc.strerror or exc}") from exc
    paths = [
        os.path.join(folder, name)
        for name in sorted(names)
        if name.endswith(".csv") and os.path.isfile(os.path.join(folder, name))
    ]
    if not paths:
        raise RuntimeProblem(f"no .csv files found in folder: {folder}")
    return paths


def read_json_file(path: str, what: str):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise RuntimeProblem(f"{what} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeProblem(f"{what} is not valid JSON: {path} ({exc})") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeProblem(f"cannot read {what} {path}: {exc}") from exc


def load_database(path: str) -> list[dict]:
    data = read_json_file(path, "JSON database")
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise RuntimeProblem(f"JSON database must be an array of objects: {path}")
    return data


def load_queries(path: str) -> dict | list:
    data = read_json_file(path, "query file")
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        return data
    raise RuntimeProblem(
        f"query file must hold a query object or an array of query objects: {path}"
    )


def write_json(path: str, data) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as exc:
        raise RuntimeProblem(f"cannot write {path}: {exc.strerror or exc}") from exc


def response_file_name() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    return f"response_{STUDENT_ID}_{FIRST_NAME}_{LAST_NAME}_{stamp}.json"


def input_csv_paths(args: argparse.Namespace) -> list[str]:
    """The CSV files to parse for -i or -d, in processing order."""
    if args.i is not None:
        if not os.path.isfile(args.i):
            raise RuntimeProblem(f"CSV file not found: {args.i}")
        return [args.i]
    return csv_paths_in_folder(args.d)


def read_airports(path: str) -> set[str]:
    try:
        return load_airports(path)
    except FileNotFoundError as exc:
        raise RuntimeProblem(f"airport list not found: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise RuntimeProblem(f"cannot read airport list {path}: {exc}") from exc


def open_log_handler(log_path: str) -> logging.Handler:
    try:
        handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    except OSError as exc:
        raise RuntimeProblem(f"cannot write {log_path}: {exc.strerror or exc}") from exc
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    return handler


def parse_and_store(paths: list[str], airports: set[str], db_path: str,
                    logger: logging.Logger) -> list[dict]:
    """Parse the CSV files, log invalid rows and write the database."""
    try:
        records, errors = parse_files(paths, airports)
    except (OSError, UnicodeError) as exc:
        raise RuntimeProblem(f"cannot read input file: {exc}") from exc
    for message in errors:
        logger.warning(message)
    logger.info("%d valid and %d invalid rows from %d file(s)",
                len(records), len(errors), len(paths))
    write_json(db_path, records)
    print(f"{len(records)} valid flights written to {db_path}, {len(errors)} invalid rows logged")
    return records


def main(argv: list[str] | None = None) -> int:
    """Run the whole program and return the exit code (0, 1 or 2).

    argv is the argument list without the program name.
    None means use sys.argv[1:] (argparse does this for you).
    """
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        # argparse exits on usage errors (code 2) and after -h (code 0).
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 2)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    handler = None
    try:
        if args.j is not None:
            db = load_database(args.j)
        else:
            paths = input_csv_paths(args)
            airports = read_airports(args.a)
            db_path = args.o if args.o is not None else "db.json"
            handler = open_log_handler(os.path.join(os.path.dirname(db_path), "errors.log"))
            logger.addHandler(handler)
            db = parse_and_store(paths, airports, db_path, logger)

        if args.q is not None:
            queries = load_queries(args.q)
            responses = run_queries(db, queries)
            folder = args.r if args.r is not None else "."
            response_path = os.path.join(folder, response_file_name())
            write_json(response_path, responses)
            print(f"{len(responses)} query result(s) written to {response_path}")
        return 0
    except RuntimeProblem as exc:
        if handler is not None:
            logger.error("%s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # last resort: never show a traceback
        if handler is not None:
            logger.error("unexpected problem: %s", exc)
        print(f"Error: unexpected problem: {exc}", file=sys.stderr)
        return 1
    finally:
        # Always detach the handler: the autograder calls main() many times
        # in one process and a leftover handler would write into later logs.
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()


if __name__ == "__main__":
    sys.exit(main())
