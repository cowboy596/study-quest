from __future__ import annotations

import json
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
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                user_answer TEXT NOT NULL DEFAULT '',
                is_correct INTEGER,
                status TEXT NOT NULL,
                attempted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
        conn.execute("DELETE FROM attempts")
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


def get_latest_attempt_status(
    question_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> str | None:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT status
            FROM attempts
            WHERE question_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (question_id,),
        ).fetchone()
    return None if row is None else str(row["status"])


def get_learning_summary(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, object]:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            WITH latest AS (
                SELECT question_id, status
                FROM attempts
                WHERE id IN (
                    SELECT MAX(id)
                    FROM attempts
                    GROUP BY question_id
                )
            )
            SELECT
                (SELECT COUNT(*) FROM questions) AS total,
                COUNT(latest.question_id) AS attempted,
                SUM(CASE WHEN latest.status = 'correct' THEN 1 ELSE 0 END) AS correct,
                SUM(CASE WHEN latest.status = 'wrong' THEN 1 ELSE 0 END) AS wrong,
                SUM(CASE WHEN latest.status = 'self_check' THEN 1 ELSE 0 END) AS self_check,
                (SELECT COUNT(*) FROM mistakes) AS mistakes,
                (SELECT MAX(attempted_at) FROM attempts) AS latest_attempted_at
            FROM questions AS q
            LEFT JOIN latest ON latest.question_id = q.id
            """
        ).fetchone()
    total = int(row["total"] or 0)
    attempted = int(row["attempted"] or 0)
    return {
        "total": total,
        "attempted": attempted,
        "unattempted": total - attempted,
        "correct": int(row["correct"] or 0),
        "wrong": int(row["wrong"] or 0),
        "self_check": int(row["self_check"] or 0),
        "mistakes": int(row["mistakes"] or 0),
        "latest_attempted_at": row["latest_attempted_at"],
    }


def get_questions_with_progress(
    db_path: str | Path = DEFAULT_DB_PATH,
    subject: str | None = None,
    question_type: str | None = None,
    learning_status: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, object]]:
    initialize_database(db_path)
    conditions: list[str] = []
    parameters: list[str] = []
    if subject:
        conditions.append("q.subject = ?")
        parameters.append(subject)
    if question_type:
        conditions.append("q.type = ?")
        parameters.append(question_type)
    if keyword:
        conditions.append("q.stem LIKE ?")
        parameters.append(f"%{keyword}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            WITH latest AS (
                SELECT a.question_id, a.user_answer, a.is_correct, a.status, a.attempted_at
                FROM attempts AS a
                WHERE a.id IN (
                    SELECT MAX(id)
                    FROM attempts
                    GROUP BY question_id
                )
            )
            SELECT
                q.*,
                latest.user_answer AS latest_user_answer,
                latest.is_correct AS latest_is_correct,
                latest.status AS latest_status,
                latest.attempted_at AS latest_attempted_at,
                CASE
                    WHEN latest.status IS NULL THEN '未做'
                    WHEN latest.status = 'correct' THEN '已做-正确'
                    WHEN latest.status = 'wrong' THEN '已做-错误'
                    WHEN latest.status = 'self_check' THEN '已做-自查'
                    ELSE latest.status
                END AS learning_status,
                CASE WHEN m.question_id IS NULL THEN 0 ELSE 1 END AS in_mistakes
            FROM questions AS q
            LEFT JOIN latest ON latest.question_id = q.id
            LEFT JOIN mistakes AS m ON m.question_id = q.id
            {where_clause}
            ORDER BY q.id DESC
            """,
            parameters,
        ).fetchall()
    rows_as_dicts = [dict(row) for row in rows]
    if not learning_status or learning_status == "全部":
        return rows_as_dicts
    if learning_status == "已做":
        return [row for row in rows_as_dicts if row["learning_status"] != "未做"]
    return [row for row in rows_as_dicts if row["learning_status"] == learning_status]


def update_question(
    question_id: int,
    data: dict[str, object],
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    initialize_database(db_path)
    question_type = str(data.get("type", "")).strip()
    if question_type not in {"single_choice", "multiple_choice", "true_false", "short_answer"}:
        raise ValueError("题型不在允许范围内。")
    required_fields = ["subject", "stem", "answer", "explanation", "difficulty"]
    for field in required_fields:
        if not str(data.get(field, "")).strip():
            raise ValueError(f"{field} 不能为空。")
    options = _normalize_question_options(data.get("options", []))
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE questions
            SET subject = ?, type = ?, stem = ?, options = ?, answer = ?,
                explanation = ?, tags = ?, difficulty = ?
            WHERE id = ?
            """,
            (
                str(data["subject"]).strip(),
                question_type,
                str(data["stem"]).strip(),
                options,
                str(data["answer"]).strip(),
                str(data["explanation"]).strip(),
                str(data.get("tags", "")).strip(),
                str(data["difficulty"]).strip(),
                question_id,
            ),
        )
        conn.commit()


def delete_question(
    question_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM attempts WHERE question_id = ?", (question_id,))
        conn.execute("DELETE FROM favorites WHERE question_id = ?", (question_id,))
        conn.execute("DELETE FROM mistakes WHERE question_id = ?", (question_id,))
        conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()


def _normalize_question_options(value: object) -> str:
    if isinstance(value, list):
        options = value
    else:
        text = str(value).strip()
        try:
            parsed = json.loads(text) if text else []
        except json.JSONDecodeError as exc:
            raise ValueError("options 必须是合法列表或 JSON 字符串。") from exc
        options = parsed
    if not isinstance(options, list) or not all(isinstance(item, str) for item in options):
        raise ValueError("options 必须是字符串列表。")
    return json.dumps(options, ensure_ascii=False)
