from __future__ import annotations

from pathlib import Path

from modules.db import DEFAULT_DB_PATH, get_connection, initialize_database


def record_attempt(
    question_id: int,
    user_answer: str,
    is_correct: bool | None,
    status: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    if status not in {"correct", "wrong", "self_check"}:
        raise ValueError("status 必须是 correct、wrong 或 self_check。")
    stored_is_correct = None if is_correct is None else int(is_correct)
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO attempts (question_id, user_answer, is_correct, status)
            VALUES (?, ?, ?, ?)
            """,
            (question_id, user_answer, stored_is_correct, status),
        )
        conn.commit()


def count_attempts(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM attempts").fetchone()
    return int(row["total"])
