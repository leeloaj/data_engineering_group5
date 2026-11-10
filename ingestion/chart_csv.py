import csv
import re
from pathlib import Path

from .bronze import input_date, region_code, spotify_track_id


def chart_csv_context(path, fallback_date=None, fallback_region=None, weekly=False):
    filename_context = re.fullmatch(
        r"charts_data_(\d{4}-\d{2}-\d{2})_([a-zA-Z]+)(_weekly)?\.csv", path.name
    )
    if filename_context:
        fallback_date = fallback_date or filename_context[1]
        fallback_region = fallback_region or filename_context[2]
        weekly = weekly or bool(filename_context[3])
    if fallback_date:
        fallback_date = input_date(fallback_date).isoformat()
    if fallback_region:
        fallback_region = region_code(fallback_region)
    return fallback_date, fallback_region, weekly


def chart_rows(reader, fallback_date, fallback_region, weekly=False):
    headers = reader.fieldnames or []
    historical = "chart" in headers
    if historical and weekly:
        raise ValueError("the Kaggle archive contains daily charts")
    id_column = next((name for name in ("id", "uri", "url") if name in headers), None)
    required = {"rank", "streams"}
    if not fallback_date:
        required.add("date")
    if not fallback_region:
        required.add("region")
    if len(headers) != len(set(headers)):
        raise ValueError("duplicate CSV headers")
    if required.difference(headers) or not id_column:
        raise ValueError("expected rank, streams, id/uri/url, and a chart date and region")

    source = "kaggle_spotify_charts" if historical else "spotify_charts"
    for row in reader:
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("column count differs from the header")
            chart_date = input_date(row.get("date", "").strip() or fallback_date or "")
            region = region_code(row.get("region", "").strip() or fallback_region or "")
            track_id = spotify_track_id(row[id_column])
            chart_type = row["chart"].strip().lower() if historical else "top200"
            if chart_type not in {"top200", "viral50"}:
                raise ValueError(f"unknown chart type: {chart_type!r}")
            if weekly:
                chart_type = "top200_weekly"
            rank = int(row["rank"])
            streams = int(row["streams"]) if row["streams"].strip() else None
            if not 0 < rank < 2**31 or (streams is not None and not 0 <= streams < 2**63):
                raise ValueError("rank must be positive and streams must be nonnegative")
        except ValueError as error:
            raise ValueError(f"CSV line {reader.line_num}: {error}") from error
        yield source, chart_date, region, chart_type, track_id, rank, streams, row


def chart_track_ids(csv_path, fallback_date=None, fallback_region=None, weekly=False):
    path = Path(csv_path)
    context = chart_csv_context(path, fallback_date, fallback_region, weekly)
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, strict=True)
        track_ids = {track_id for _, _, _, _, track_id, _, _, _ in chart_rows(reader, *context)}
    if not track_ids:
        raise ValueError("CSV contains no chart rows")
    return sorted(track_ids)
