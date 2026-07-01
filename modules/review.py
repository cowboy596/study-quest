from __future__ import annotations

from pathlib import Path

from modules.db import DEFAULT_DB_PATH, get_connection, initialize_database

REVIEW_MODE_ALL = "all"
REVIEW_MODE_UNATTEMPTED = "unattempted"
REVIEW_MODE_MISTAKES = "mistakes"
REVIEW_MODE_WRONG = "wrong"
REVIEW_MODE_CORRECT = "correct"
REVIEW_MODE_SELF_CHECK = "self_check"

REVIEW_MODE_LABELS = {
    REVIEW_MODE_ALL: "全部题目复习",
    REVIEW_MODE_UNATTEMPTED: "未做题复习",
    REVIEW_MODE_MISTAKES: "错题集复习",
    REVIEW_MODE_WRONG: "已做错误题复习",
    REVIEW_MODE_CORRECT: "已做正确题复习",
    REVIEW_MODE_SELF_CHECK: "简答自查题复习",
}

LATEST_STATUS_BY_MODE = {
    REVIEW_MODE_WRONG: "wrong",
    REVIEW_MODE_CORRECT: "correct",
    REVIEW_MODE_SELF_CHECK: "self_check",
}


def count_review_questions(
    db_path: str | Path = DEFAULT_DB_PATH,
    mode: str = REVIEW_MODE_ALL,
    subject: str | None = None,
    question_type: str | None = None,
) -> int:
    initialize_database(db_path)
    query, parameters = _build_review_query(
        mode,
        subject=subject,
        question_type=question_type,
        count_only=True,
    )
    with get_connection(db_path) as conn:
        row = conn.execute(query, parameters).fetchone()
    return int(row["total"] or 0)


def get_review_questions(
    db_path: str | Path = DEFAULT_DB_PATH,
    mode: str = REVIEW_MODE_ALL,
    subject: str | None = None,
    question_type: str | None = None,
    count: int = 5,
) -> list[dict[str, object]]:
    initialize_database(db_path)
    query, parameters = _build_review_query(
        mode,
        subject=subject,
        question_type=question_type,
        count_only=False,
    )
    limit = max(1, int(count))
    with get_connection(db_path) as conn:
        rows = conn.execute(f"{query} ORDER BY RANDOM() LIMIT ?", [*parameters, limit]).fetchall()
    return [dict(row) for row in rows]


def _build_review_query(
    mode: str,
    subject: str | None,
    question_type: str | None,
    count_only: bool,
) -> tuple[str, list[str]]:
    conditions: list[str] = []
    parameters: list[str] = []

    if subject:
        conditions.append("q.subject = ?")
        parameters.append(subject)
    if question_type:
        conditions.append("q.type = ?")
        parameters.append(question_type)

    if mode == REVIEW_MODE_UNATTEMPTED:
        conditions.append("latest.question_id IS NULL")
    elif mode == REVIEW_MODE_MISTAKES:
        conditions.append("m.question_id IS NOT NULL")
    elif mode in LATEST_STATUS_BY_MODE:
        conditions.append("latest.status = ?")
        parameters.append(LATEST_STATUS_BY_MODE[mode])
    elif mode != REVIEW_MODE_ALL:
        raise ValueError("未知复习模式。")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    projection = "COUNT(*) AS total" if count_only else _review_projection()
    return (
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
        SELECT {projection}
        FROM questions AS q
        LEFT JOIN latest ON latest.question_id = q.id
        LEFT JOIN mistakes AS m ON m.question_id = q.id
        {where_clause}
        """,
        parameters,
    )


def _review_projection() -> str:
    return """
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
    """
