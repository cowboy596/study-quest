from __future__ import annotations

from pathlib import Path

from modules.db import DEFAULT_DB_PATH, get_connection, initialize_database


def add_mistake(
    question_id: int,
    user_answer: str,
    correct_answer: str,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO mistakes (question_id, user_answer, correct_answer)
            VALUES (?, ?, ?)
            """,
            (question_id, user_answer, correct_answer),
        )
        inserted = cursor.rowcount == 1
        if not inserted:
            conn.execute(
                """
                UPDATE mistakes
                SET user_answer = ?, correct_answer = ?, created_at = CURRENT_TIMESTAMP
                WHERE question_id = ?
                """,
                (user_answer, correct_answer, question_id),
            )
        conn.commit()
    return inserted


def remove_mistake(
    question_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM mistakes WHERE question_id = ?", (question_id,))
        conn.commit()


def list_mistakes(
    db_path: str | Path = DEFAULT_DB_PATH,
    subject: str | None = None,
) -> list[dict[str, object]]:
    initialize_database(db_path)
    where_clause = " WHERE q.subject = ?" if subject else ""
    parameters = (subject,) if subject else ()
    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                m.question_id, m.user_answer, m.correct_answer,
                m.created_at AS added_at,
                q.subject, q.type, q.stem, q.options, q.explanation
            FROM mistakes AS m
            JOIN questions AS q ON q.id = m.question_id
            {where_clause}
            ORDER BY m.created_at DESC, m.id DESC
            """,
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]


def add_favorite(
    question_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> bool:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO favorites (question_id) VALUES (?)",
            (question_id,),
        )
        conn.commit()
    return cursor.rowcount == 1


def remove_favorite(
    question_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM favorites WHERE question_id = ?", (question_id,))
        conn.commit()


def list_favorites(
    db_path: str | Path = DEFAULT_DB_PATH,
    subject: str | None = None,
) -> list[dict[str, object]]:
    initialize_database(db_path)
    where_clause = " WHERE q.subject = ?" if subject else ""
    parameters = (subject,) if subject else ()
    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT
                f.question_id, f.created_at AS added_at,
                q.subject, q.type, q.stem, q.options,
                q.answer AS correct_answer, q.explanation
            FROM favorites AS f
            JOIN questions AS q ON q.id = f.question_id
            {where_clause}
            ORDER BY f.created_at DESC, f.id DESC
            """,
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]


def count_favorites(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM favorites").fetchone()
    return int(row["total"])
