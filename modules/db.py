from __future__ import annotations

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "study_quest.db"


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL,
                type TEXT NOT NULL,
                stem TEXT NOT NULL,
                options TEXT NOT NULL,
                answer TEXT NOT NULL,
                explanation TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '',
                difficulty TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                user_answer TEXT NOT NULL DEFAULT '',
                correct_answer TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            )
            """
        )
        conn.execute(
            """
            DELETE FROM questions
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM questions
                GROUP BY subject, type, stem, answer
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_dedupe
            ON questions (subject, type, stem, answer)
            """
        )
        conn.execute(
            """
            DELETE FROM mistakes
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM mistakes
                GROUP BY question_id
            )
            """
        )
        conn.execute(
            """
            DELETE FROM favorites
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM favorites
                GROUP BY question_id
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mistakes_question
            ON mistakes (question_id)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_question
            ON favorites (question_id)
            """
        )
        conn.commit()


def count_questions(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM questions").fetchone()
    return int(row["total"])


def count_mistakes(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM mistakes").fetchone()
    return int(row["total"])


def clear_all_questions(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM favorites")
        conn.execute("DELETE FROM mistakes")
        conn.execute("DELETE FROM questions")
        conn.commit()


def get_subjects(db_path: str | Path = DEFAULT_DB_PATH) -> list[str]:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT subject FROM questions ORDER BY subject"
        ).fetchall()
    return [str(row["subject"]) for row in rows]


def get_question_types(db_path: str | Path = DEFAULT_DB_PATH) -> list[str]:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT type FROM questions ORDER BY type"
        ).fetchall()
    return [str(row["type"]) for row in rows]


def _question_filter(
    subject: str | None,
    question_type: str | None,
) -> tuple[str, list[str]]:
    conditions: list[str] = []
    parameters: list[str] = []
    if subject:
        conditions.append("subject = ?")
        parameters.append(subject)
    if question_type:
        conditions.append("type = ?")
        parameters.append(question_type)
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, parameters


def count_matching_questions(
    db_path: str | Path = DEFAULT_DB_PATH,
    subject: str | None = None,
    question_type: str | None = None,
) -> int:
    initialize_database(db_path)
    where_clause, parameters = _question_filter(subject, question_type)
    with get_connection(db_path) as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS total FROM questions{where_clause}",
            parameters,
        ).fetchone()
    return int(row["total"])


def get_random_questions(
    db_path: str | Path = DEFAULT_DB_PATH,
    subject: str | None = None,
    question_type: str | None = None,
    count: int = 5,
) -> list[dict[str, object]]:
    initialize_database(db_path)
    where_clause, parameters = _question_filter(subject, question_type)
    limit = max(1, int(count))
    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM questions{where_clause} ORDER BY RANDOM() LIMIT ?",
            [*parameters, limit],
        ).fetchall()
    return [dict(row) for row in rows]
