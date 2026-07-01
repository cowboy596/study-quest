from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import BinaryIO, Iterable, Mapping

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
SUPPORTED_IMPORT_EXTENSIONS = {".csv", ".xlsx", ".json", ".md", ".txt"}
SUPPORTED_QUESTION_TYPES = {
    "single_choice",
    "multiple_choice",
    "true_false",
    "short_answer",
}


@dataclass(frozen=True)
class ImportResult:
    total_rows: int
    inserted_rows: int
    skipped_duplicates: int


@dataclass(frozen=True)
class ParseResult:
    total_rows: int
    questions: list[dict[str, object]]
    errors: list[str]

    @property
    def failed_rows(self) -> int:
        return len(self.errors)


class ImportValidationError(ValueError):
    """Raised when an uploaded question-bank file cannot be parsed."""


def import_questions_csv(
    csv_file: str | Path | BinaryIO,
    db_path: str | Path = DEFAULT_DB_PATH,
    source: str = "uploaded_csv",
) -> ImportResult:
    parsed = _parse_csv(csv_file)
    if parsed.errors:
        raise ImportValidationError("; ".join(parsed.errors))
    return save_questions(
        parsed.questions,
        db_path=db_path,
        source=source,
    )


def parse_questions_file(file: str | Path | BinaryIO) -> ParseResult:
    suffix = _file_suffix(file)
    if suffix not in SUPPORTED_IMPORT_EXTENSIONS:
        raise ImportValidationError(f"不支持的文件格式：{suffix or '未知'}")
    if suffix == ".csv":
        return _parse_csv(file)
    if suffix == ".xlsx":
        return _parse_xlsx(file)
    if suffix == ".json":
        return _parse_json(file)
    return _parse_markdown_text(file)


def save_questions(
    questions: Iterable[Mapping[str, object]],
    db_path: str | Path = DEFAULT_DB_PATH,
    source: str = "uploaded_csv",
) -> ImportResult:
    initialize_database(db_path)
    rows = list(questions)
    total_rows = len(rows)
    inserted_rows = 0
    skipped_duplicates = 0

    with get_connection(db_path) as conn:
        for row in rows:
            values = (
                source,
                _clean(row["subject"]),
                _clean(row["type"]),
                _clean(row["stem"]),
                _normalize_options(row["options"]),
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


def _parse_csv(file: str | Path | BinaryIO) -> ParseResult:
    _reset_file(file)
    frame = pd.read_csv(file)
    return _parse_frame(frame)


def _parse_xlsx(file: str | Path | BinaryIO) -> ParseResult:
    _reset_file(file)
    frame = pd.read_excel(file)
    return _parse_frame(frame)


def _parse_frame(frame: pd.DataFrame) -> ParseResult:
    if frame.empty:
        raise ImportValidationError("题库文件为空。")
    _validate_columns(frame)
    return _parse_rows(_rows_from_frame(frame))


def _parse_json(file: str | Path | BinaryIO) -> ParseResult:
    text = _read_text(file)
    if not text.strip():
        raise ImportValidationError("题库文件为空。")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportValidationError("JSON 文件不是合法 JSON。") from exc
    if isinstance(payload, dict):
        rows = payload.get("questions")
        if rows is None:
            raise ImportValidationError("JSON 对象必须包含 questions 列表。")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ImportValidationError("JSON 题目必须是列表。")
    if not rows:
        raise ImportValidationError("题库文件为空。")
    return _parse_rows(rows)


def _parse_markdown_text(file: str | Path | BinaryIO) -> ParseResult:
    text = _read_text(file)
    if not text.strip():
        raise ImportValidationError("题库文件为空。")
    blocks = [block.strip() for block in re.split(r"(?m)^---+\s*$", text) if block.strip()]
    if not blocks:
        raise ImportValidationError("Markdown/TXT 文件不符合题目模板。")
    rows: list[dict[str, object]] = []
    block_errors: list[str] = []
    for index, block in enumerate(blocks, start=1):
        try:
            rows.append(_parse_template_block(block, index))
        except ImportValidationError as exc:
            block_errors.append(str(exc))
    parsed = _parse_rows(rows)
    return ParseResult(
        total_rows=len(blocks),
        questions=parsed.questions,
        errors=[*block_errors, *parsed.errors],
    )


def _parse_template_block(block: str, index: int) -> dict[str, object]:
    row: dict[str, object] = {}
    current_key: str | None = None
    option_lines: list[str] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or re.fullmatch(r"-{5,}", line):
            continue
        key_match = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if key_match:
            key = key_match.group(1)
            value = key_match.group(2).strip()
            current_key = key
            if key == "options":
                option_lines = []
                row[key] = option_lines
                if value:
                    option_lines.append(value)
            else:
                row[key] = value
            continue
        if current_key == "options":
            option_lines.append(line)
        else:
            raise ImportValidationError(
                f"第 {index} 题不符合 Markdown/TXT 模板，问题位置：{line}"
            )
    return row


def _parse_rows(rows: Iterable[Mapping[str, object]]) -> ParseResult:
    valid_questions: list[dict[str, object]] = []
    errors: list[str] = []
    materialized = list(rows)
    for index, row in enumerate(materialized, start=1):
        try:
            valid_questions.append(_validate_question_row(row, index))
        except ImportValidationError as exc:
            errors.append(str(exc))
    return ParseResult(
        total_rows=len(materialized),
        questions=valid_questions,
        errors=errors,
    )


def _validate_question_row(row: Mapping[str, object], index: int) -> dict[str, object]:
    missing = [column for column in REQUIRED_COLUMNS if column not in row]
    if missing:
        raise ImportValidationError(
            f"第 {index} 题缺少必需字段：{', '.join(missing)}"
        )
    question_type = _clean(row["type"])
    if question_type not in SUPPORTED_QUESTION_TYPES:
        raise ImportValidationError(
            f"第 {index} 题题型必须是以下之一：{', '.join(sorted(SUPPORTED_QUESTION_TYPES))}"
        )
    answer = _clean(row["answer"])
    if not answer:
        raise ImportValidationError(f"第 {index} 题答案不能为空。")
    explanation = _clean(row["explanation"])
    if not explanation:
        raise ImportValidationError(f"第 {index} 题解析不能为空。")
    normalized_options = _normalize_options(row["options"])
    options = json.loads(normalized_options)
    return {
        "subject": _required_text(row["subject"], "subject", index),
        "type": question_type,
        "stem": _required_text(row["stem"], "stem", index),
        "options": options,
        "answer": answer,
        "explanation": explanation,
        "tags": _clean(row["tags"]),
        "difficulty": _required_text(row["difficulty"], "difficulty", index),
    }


def _rows_from_frame(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for _, row in frame.iterrows():
        rows.append({column: row[column] for column in REQUIRED_COLUMNS})
    return rows


def _validate_columns(frame: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        joined = ", ".join(missing)
        raise ImportValidationError(f"题库文件缺少必需字段：{joined}")


def _normalize_options(value: object) -> str:
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ImportValidationError("options 必须是字符串数组。")
        return json.dumps(value, ensure_ascii=False)
    text = _clean(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportValidationError("options 必须是合法的 JSON 数组字符串。") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ImportValidationError("options 必须是字符串数组。")
    return json.dumps(parsed, ensure_ascii=False)


def _required_text(value: object, field: str, index: int) -> str:
    text = _clean(value)
    if not text:
        raise ImportValidationError(f"第 {index} 题字段 {field} 不能为空。")
    return text


def _file_suffix(file: str | Path | BinaryIO) -> str:
    name = getattr(file, "name", "")
    path = Path(str(name or file))
    return path.suffix.lower()


def _read_text(file: str | Path | BinaryIO) -> str:
    if isinstance(file, (str, Path)):
        return Path(file).read_text(encoding="utf-8")
    _reset_file(file)
    data = file.read()
    if isinstance(data, bytes):
        return data.decode("utf-8-sig")
    return str(data)


def _reset_file(file: object) -> None:
    seek = getattr(file, "seek", None)
    if callable(seek):
        seek(0)


def _clean(value: object) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if pd.isna(value):
        return ""
    return str(value).strip()
