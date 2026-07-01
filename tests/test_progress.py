import json

from modules.db import (
    count_mistakes,
    count_questions,
    delete_question,
    get_connection,
    get_learning_summary,
    get_questions_with_progress,
    initialize_database,
    update_question,
)
from modules.mistakes import add_mistake, remove_mistake
from modules.progress import count_attempts, record_attempt


def _question_ids(db_path):
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT id, stem FROM questions ORDER BY id").fetchall()
    return {row["stem"]: int(row["id"]) for row in rows}


def test_initialize_database_creates_attempts_table(tmp_path):
    db_path = tmp_path / "study_quest.db"

    initialize_database(db_path)

    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='attempts'"
        ).fetchone()
    assert row["name"] == "attempts"


def test_record_attempt_persists_objective_quiz_result(seeded_db):
    question_id = _question_ids(seeded_db)["Python single 1?"]

    record_attempt(question_id, "A. One", True, "correct", seeded_db)

    with get_connection(seeded_db) as conn:
        row = conn.execute("SELECT * FROM attempts WHERE question_id = ?", (question_id,)).fetchone()
    assert row["user_answer"] == "A. One"
    assert row["is_correct"] == 1
    assert row["status"] == "correct"


def test_record_attempt_persists_short_answer_self_check(seeded_db):
    question_id = _question_ids(seeded_db)["Explain TCP."]

    record_attempt(question_id, "TCP 是传输层协议。", None, "self_check", seeded_db)

    with get_connection(seeded_db) as conn:
        row = conn.execute("SELECT * FROM attempts WHERE question_id = ?", (question_id,)).fetchone()
    assert row["is_correct"] is None
    assert row["status"] == "self_check"


def test_manage_progress_status_labels_include_correct_wrong_unseen_and_self_check(seeded_db):
    ids = _question_ids(seeded_db)
    record_attempt(ids["Python single 1?"], "A. One", True, "correct", seeded_db)
    record_attempt(ids["TCP is connection-oriented."], "错误", False, "wrong", seeded_db)
    record_attempt(ids["Explain TCP."], "TCP 是传输层协议。", None, "self_check", seeded_db)

    rows = get_questions_with_progress(seeded_db)
    by_stem = {row["stem"]: row for row in rows}

    assert by_stem["Python single 1?"]["learning_status"] == "已做-正确"
    assert by_stem["TCP is connection-oriented."]["learning_status"] == "已做-错误"
    assert by_stem["Explain TCP."]["learning_status"] == "已做-自查"
    assert by_stem["Python single 2?"]["learning_status"] == "未做"


def test_manage_filters_by_subject_type_status_and_keyword(seeded_db):
    ids = _question_ids(seeded_db)
    record_attempt(ids["Python single 1?"], "A. One", True, "correct", seeded_db)
    record_attempt(ids["TCP is connection-oriented."], "错误", False, "wrong", seeded_db)

    assert all(row["subject"] == "Python" for row in get_questions_with_progress(seeded_db, subject="Python"))
    assert all(row["type"] == "true_false" for row in get_questions_with_progress(seeded_db, question_type="true_false"))

    correct_rows = get_questions_with_progress(seeded_db, learning_status="已做-正确")
    assert [row["stem"] for row in correct_rows] == ["Python single 1?"]

    unseen_rows = get_questions_with_progress(seeded_db, learning_status="未做")
    assert "Python single 2?" in {row["stem"] for row in unseen_rows}
    assert "TCP is connection-oriented." not in {row["stem"] for row in unseen_rows}

    keyword_rows = get_questions_with_progress(seeded_db, keyword="multiple")
    assert [row["stem"] for row in keyword_rows] == ["Python multiple?"]


def test_learning_summary_counts_latest_attempt_statuses(seeded_db):
    ids = _question_ids(seeded_db)
    record_attempt(ids["Python single 1?"], "B. Two", False, "wrong", seeded_db)
    record_attempt(ids["Python single 1?"], "A. One", True, "correct", seeded_db)
    record_attempt(ids["TCP is connection-oriented."], "错误", False, "wrong", seeded_db)
    record_attempt(ids["Explain TCP."], "TCP 是传输层协议。", None, "self_check", seeded_db)
    add_mistake(ids["TCP is connection-oriented."], "错误", "True", seeded_db)

    summary = get_learning_summary(seeded_db)

    assert summary == {
        "total": 5,
        "attempted": 3,
        "unattempted": 2,
        "correct": 1,
        "wrong": 1,
        "self_check": 1,
        "mistakes": 1,
        "latest_attempted_at": summary["latest_attempted_at"],
    }
    assert summary["latest_attempted_at"] is not None


def test_update_question_updates_questions_table(seeded_db):
    question_id = _question_ids(seeded_db)["Python single 1?"]

    update_question(
        question_id,
        {
            "subject": "Python 基础",
            "type": "single_choice",
            "stem": "Python 的解释器是什么？",
            "options": ["A. CPython", "B. HTML"],
            "answer": "A",
            "explanation": "CPython 是常见解释器实现。",
            "tags": "python",
            "difficulty": "medium",
        },
        seeded_db,
    )

    with get_connection(seeded_db) as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    assert row["subject"] == "Python 基础"
    assert row["options"] == json.dumps(["A. CPython", "B. HTML"], ensure_ascii=False)


def test_delete_question_cleans_questions_mistakes_and_attempts(seeded_db):
    question_id = _question_ids(seeded_db)["Python single 1?"]
    add_mistake(question_id, "B", "A", seeded_db)
    record_attempt(question_id, "B", False, "wrong", seeded_db)

    delete_question(question_id, seeded_db)

    assert count_questions(seeded_db) == 4
    assert count_mistakes(seeded_db) == 0
    assert count_attempts(seeded_db) == 0


def test_mistake_add_remove_from_manage_operations_remain_unique(seeded_db):
    question_id = _question_ids(seeded_db)["Python single 1?"]

    assert add_mistake(question_id, "", "A", seeded_db) is True
    assert add_mistake(question_id, "", "A", seeded_db) is False
    assert count_mistakes(seeded_db) == 1

    remove_mistake(question_id, seeded_db)

    rows = get_questions_with_progress(seeded_db)
    row = next(item for item in rows if item["id"] == question_id)
    assert count_mistakes(seeded_db) == 0
    assert row["in_mistakes"] == 0
