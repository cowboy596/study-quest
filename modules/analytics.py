from __future__ import annotations

from pathlib import Path

from modules.db import DEFAULT_DB_PATH, get_connection, initialize_database


def get_overall_stats(db_path: str | Path = DEFAULT_DB_PATH) -> dict[str, object]:
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
                (SELECT COUNT(*) FROM questions) AS total_questions,
                (SELECT COUNT(DISTINCT question_id) FROM attempts) AS attempted_questions,
                (SELECT COUNT(*) FROM attempts) AS total_attempts,
                (SELECT COUNT(*) FROM attempts WHERE status IN ('correct', 'wrong')) AS objective_attempts,
                (SELECT COUNT(*) FROM attempts WHERE status = 'correct') AS objective_correct,
                (SELECT COUNT(*) FROM attempts WHERE status = 'wrong') AS objective_wrong,
                (SELECT COUNT(*) FROM mistakes) AS mistakes,
                (SELECT MAX(attempted_at) FROM attempts) AS latest_attempted_at,
                (
                    SELECT COUNT(*)
                    FROM attempts
                    WHERE attempted_at >= datetime('now', '-7 days')
                ) AS recent_7_day_attempts
            """
        ).fetchone()
    total_questions = int(row["total_questions"] or 0)
    attempted_questions = int(row["attempted_questions"] or 0)
    objective_attempts = int(row["objective_attempts"] or 0)
    objective_correct = int(row["objective_correct"] or 0)
    return {
        "total_questions": total_questions,
        "attempted_questions": attempted_questions,
        "unattempted_questions": total_questions - attempted_questions,
        "total_attempts": int(row["total_attempts"] or 0),
        "objective_attempts": objective_attempts,
        "objective_correct": objective_correct,
        "objective_wrong": int(row["objective_wrong"] or 0),
        "objective_accuracy": _accuracy(objective_correct, objective_attempts),
        "mistakes": int(row["mistakes"] or 0),
        "latest_attempted_at": row["latest_attempted_at"],
        "recent_7_day_attempts": int(row["recent_7_day_attempts"] or 0),
    }


def get_subject_stats(db_path: str | Path = DEFAULT_DB_PATH) -> list[dict[str, object]]:
    return _group_stats(db_path, group_field="subject")


def get_type_stats(db_path: str | Path = DEFAULT_DB_PATH) -> list[dict[str, object]]:
    return _group_stats(db_path, group_field="type")


def get_weak_subjects(
    db_path: str | Path = DEFAULT_DB_PATH,
    limit: int = 5,
) -> list[dict[str, object]]:
    rows = [
        row
        for row in get_subject_stats(db_path)
        if int(row["objective_done"]) > 0
    ]
    return sorted(rows, key=lambda row: (float(row["accuracy"]), -int(row["mistakes"])))[:limit]


def get_weak_question_types(
    db_path: str | Path = DEFAULT_DB_PATH,
    limit: int = 5,
) -> list[dict[str, object]]:
    rows = [
        row
        for row in get_type_stats(db_path)
        if row["type"] != "short_answer" and int(row["objective_done"]) > 0
    ]
    return sorted(rows, key=lambda row: (float(row["accuracy"]), -int(row["mistakes"])))[:limit]


def get_recent_attempts(
    db_path: str | Path = DEFAULT_DB_PATH,
    limit: int = 20,
) -> list[dict[str, object]]:
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                a.id AS attempt_id,
                a.attempted_at,
                a.question_id,
                q.stem,
                q.subject,
                q.type,
                a.user_answer,
                q.answer AS correct_answer,
                a.status,
                a.is_correct
            FROM attempts AS a
            JOIN questions AS q ON q.id = a.question_id
            ORDER BY a.attempted_at DESC, a.id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [_format_recent_attempt(dict(row)) for row in rows]


def get_review_recommendations(db_path: str | Path = DEFAULT_DB_PATH) -> list[str]:
    overall = get_overall_stats(db_path)
    weak_subjects = get_weak_subjects(db_path, limit=1)
    weak_types = get_weak_question_types(db_path, limit=1)
    recommendations: list[str] = []

    if int(overall["mistakes"]) > 0:
        recommendations.append(
            f"建议 1：优先复习错题集，目前共有 {overall['mistakes']} 道错题。"
        )
    if weak_subjects:
        subject = weak_subjects[0]
        recommendations.append(
            f"建议 2：薄弱主题为 {subject['subject']}，当前正确率 {subject['accuracy']}%。"
        )
    if weak_types:
        question_type = weak_types[0]
        recommendations.append(
            f"建议 3：薄弱题型为 {question_type['type']}，建议进入 Review 页面选择该题型专项练习。"
        )
    if int(overall["unattempted_questions"]) > 0:
        recommendations.append(
            f"建议 4：还有 {overall['unattempted_questions']} 道未做题，建议继续练习未做题。"
        )
    if int(overall["recent_7_day_attempts"]) == 0:
        recommendations.append("建议 5：最近 7 天没有练习，建议开始一次复习。")

    return recommendations or ["暂无明显薄弱项，请继续保持练习。"]


def _group_stats(db_path: str | Path, group_field: str) -> list[dict[str, object]]:
    if group_field not in {"subject", "type"}:
        raise ValueError("group_field 必须是 subject 或 type。")
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            WITH latest AS (
                SELECT a.question_id, a.status, a.attempted_at
                FROM attempts AS a
                WHERE a.id IN (
                    SELECT MAX(id)
                    FROM attempts
                    GROUP BY question_id
                )
            )
            SELECT
                q.{group_field} AS group_value,
                COUNT(q.id) AS total_questions,
                COUNT(latest.question_id) AS attempted_questions,
                SUM(CASE WHEN latest.status = 'correct' THEN 1 ELSE 0 END) AS correct,
                SUM(CASE WHEN latest.status = 'wrong' THEN 1 ELSE 0 END) AS wrong,
                SUM(CASE WHEN latest.status = 'self_check' THEN 1 ELSE 0 END) AS self_check,
                COUNT(m.question_id) AS mistakes,
                MAX(latest.attempted_at) AS latest_attempted_at
            FROM questions AS q
            LEFT JOIN latest ON latest.question_id = q.id
            LEFT JOIN mistakes AS m ON m.question_id = q.id
            GROUP BY q.{group_field}
            ORDER BY q.{group_field}
            """
        ).fetchall()
    return [_format_group_row(dict(row), group_field) for row in rows]


def _format_group_row(row: dict[str, object], group_field: str) -> dict[str, object]:
    total_questions = int(row["total_questions"] or 0)
    attempted_questions = int(row["attempted_questions"] or 0)
    correct = int(row["correct"] or 0)
    wrong = int(row["wrong"] or 0)
    objective_done = correct + wrong
    return {
        group_field: row["group_value"],
        "total_questions": total_questions,
        "attempted_questions": attempted_questions,
        "unattempted_questions": total_questions - attempted_questions,
        "correct": correct,
        "wrong": wrong,
        "self_check": int(row["self_check"] or 0),
        "objective_done": objective_done,
        "accuracy": _accuracy(correct, objective_done),
        "mistakes": int(row["mistakes"] or 0),
        "latest_attempted_at": row["latest_attempted_at"],
    }


def _format_recent_attempt(row: dict[str, object]) -> dict[str, object]:
    stem = str(row["stem"])
    summary = stem if len(stem) <= 60 else f"{stem[:60]}..."
    return {
        "attempt_id": int(row["attempt_id"]),
        "attempted_at": row["attempted_at"],
        "question_id": int(row["question_id"]),
        "stem_summary": summary,
        "subject": row["subject"],
        "type": row["type"],
        "user_answer": row["user_answer"],
        "correct_answer": row["correct_answer"],
        "status": row["status"],
        "is_correct": row["is_correct"],
    }


def _accuracy(correct: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(correct * 100 / total, 1)
