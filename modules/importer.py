from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from modules.db import DEFAULT_DB_PATH, get_connection, initialize_database

REQUIRED_COLUMNS = [
    "subject",
    "type",
    "stem",
    "options",
    "answer",
    "explanation",
    "tags",
    "difficulty",
]


@dataclass(frozen=True)
class ImportResult:
    total_rows: int
    inserted_rows: int
    skipped_duplicates: int


class ImportValidationError(ValueError):
    """Raised when an uploaded CSV does not match the V0.1 schema."""


def import_questions_csv(
    csv_file: str | Path | BinaryIO,
    db_path: str | Path = DEFAULT_DB_PATH,
    source: str = "uploaded_csv",
) -> ImportResult:
    initialize_database(db_path)
    frame = pd.read_csv(csv_file)
    _validate_columns(frame)

    total_rows = len(frame)
    inserted_rows = 0
    skipped_duplicates = 0

    with get_connection(db_path) as conn:
        for _, row in frame.iterrows():
            options = _normalize_options(row["options"])
            values = (
                source,
                _clean(row["subject"]),
                _clean(row["type"]),
                _clean(row["stem"]),
                options,
                _clean(row["answer"]),
                _clean(row["explanation"]),
                _clean(row["tags"]),
                _clean(row["difficulty"]),
            )
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO questions (
                    source, subject, type, stem, options, answer,
                    explanation, tags, difficulty
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            if cursor.rowcount == 1:
                inserted_rows += 1
            else:
                skipped_duplicates += 1
        conn.commit()

    return ImportResult(
        total_rows=total_rows,
        inserted_rows=inserted_rows,
        skipped_duplicates=skipped_duplicates,
    )


def _rows_from_frame(frame: pd.DataFrame, source: str) -> list[tuple[str, ...]]:
    rows = []
    for _, row in frame.iterrows():
        options = _normalize_options(row["options"])
        rows.append(
            (
                source,
                _clean(row["subject"]),
                _clean(row["type"]),
                _clean(row["stem"]),
                options,
                _clean(row["answer"]),
                _clean(row["explanation"]),
                _clean(row["tags"]),
                _clean(row["difficulty"]),
            )
        )
    return rows


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        joined = ", ".join(missing)
        raise ImportValidationError(f"CSV is missing required columns: {joined}")


def _normalize_options(value: object) -> str:
    text = _clean(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportValidationError("options must be a JSON array string") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ImportValidationError("options must be a JSON array of strings")
    return json.dumps(parsed, ensure_ascii=False)


def _clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()
