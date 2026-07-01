from modules.db import get_connection, get_learning_summary
from modules.mistakes import add_mistake
from modules.progress import count_attempts, record_attempt
from modules.review import (
    REVIEW_MODE_ALL,
    REVIEW_MODE_CORRECT,
    REVIEW_MODE_MISTAKES,
    REVIEW_MODE_SELF_CHECK,
    REVIEW_MODE_UNATTEMPTED,
    REVIEW_MODE_WRONG,
    count_review_questions,
    get_review_questions,
)

import app as studyquest_app


def _question_ids(db_path):
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT id, stem FROM questions ORDER BY id").fetchall()
    return {row["stem"]: int(row["id"]) for row in rows}


def _stems(rows):
    return {str(row["stem"]) for row in rows}


def test_unattempted_review_filters_questions_without_attempts(seeded_db):
    ids = _question_ids(seeded_db)
    record_attempt(ids["Python single 1?"], "A", True, "correct", seeded_db)

    rows = get_review_questions(seeded_db, REVIEW_MODE_UNATTEMPTED, count=10)

    assert "Python single 1?" not in _stems(rows)
    assert _stems(rows) == {
        "Python single 2?",
        "Python multiple?",
        "TCP is connection-oriented.",
        "Explain TCP.",
    }


def test_mistakes_review_filters_questions_in_mistakes(seeded_db):
    ids = _question_ids(seeded_db)
    add_mistake(ids["TCP is connection-oriented."], "False", "True", seeded_db)

    rows = get_review_questions(seeded_db, REVIEW_MODE_MISTAKES, count=10)

    assert _stems(rows) == {"TCP is connection-oriented."}


def test_review_filters_by_latest_wrong_correct_and_self_check_status(seeded_db):
    ids = _question_ids(seeded_db)
    record_attempt(ids["Python single 1?"], "B", False, "wrong", seeded_db)
    record_attempt(ids["Python single 1?"], "A", True, "correct", seeded_db)
    record_attempt(ids["Python single 2?"], "A", False, "wrong", seeded_db)
    record_attempt(ids["Explain TCP."], "TCP", None, "self_check", seeded_db)

    wrong_rows = get_review_questions(seeded_db, REVIEW_MODE_WRONG, count=10)
    correct_rows = get_review_questions(seeded_db, REVIEW_MODE_CORRECT, count=10)
    self_check_rows = get_review_questions(seeded_db, REVIEW_MODE_SELF_CHECK, count=10)

    assert _stems(wrong_rows) == {"Python single 2?"}
    assert _stems(correct_rows) == {"Python single 1?"}
    assert _stems(self_check_rows) == {"Explain TCP."}


def test_review_subject_and_type_filters_apply_to_pool(seeded_db):
    rows = get_review_questions(
        seeded_db,
        REVIEW_MODE_ALL,
        subject="Python",
        question_type="single_choice",
        count=10,
    )

    assert _stems(rows) == {"Python single 1?", "Python single 2?"}


def test_review_count_larger_than_available_returns_available_questions(seeded_db):
    rows = get_review_questions(
        seeded_db,
        REVIEW_MODE_ALL,
        subject="Networking",
        count=10,
    )

    assert len(rows) == 2
    assert count_review_questions(seeded_db, REVIEW_MODE_ALL, subject="Networking") == 2


def test_review_submit_records_attempt_and_adds_wrong_objective_to_mistakes(seeded_db):
    question_id = _question_ids(seeded_db)["Python single 1?"]

    result = studyquest_app._submit_review_answer(
        {
            "id": question_id,
            "type": "single_choice",
            "options": '["A. One", "B. Two"]',
            "answer": "A",
            "explanation": "Explanation",
        },
        "B. Two",
        seeded_db,
    )

    assert result["status"] == "incorrect"
    assert count_attempts(seeded_db) == 1
    with get_connection(seeded_db) as conn:
        row = conn.execute("SELECT question_id FROM mistakes").fetchone()
    assert int(row["question_id"]) == question_id


def test_review_submit_correct_mistake_can_remove_from_mistakes(seeded_db):
    question_id = _question_ids(seeded_db)["Python single 1?"]
    add_mistake(question_id, "B", "A", seeded_db)

    result = studyquest_app._submit_review_answer(
        {
            "id": question_id,
            "type": "single_choice",
            "options": '["A. One", "B. Two"]',
            "answer": "A",
            "explanation": "Explanation",
        },
        "A. One",
        seeded_db,
    )
    studyquest_app._remove_review_mistake(question_id, seeded_db)

    assert result["status"] == "correct"
    with get_connection(seeded_db) as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM mistakes").fetchone()
    assert int(row["total"]) == 0


def test_home_learning_summary_includes_latest_attempt_time(seeded_db):
    ids = _question_ids(seeded_db)
    record_attempt(ids["Python single 1?"], "A", True, "correct", seeded_db)
    record_attempt(ids["TCP is connection-oriented."], "False", False, "wrong", seeded_db)
    record_attempt(ids["Explain TCP."], "TCP", None, "self_check", seeded_db)
    add_mistake(ids["TCP is connection-oriented."], "False", "True", seeded_db)

    summary = get_learning_summary(seeded_db)

    assert summary["total"] == 5
    assert summary["attempted"] == 3
    assert summary["unattempted"] == 2
    assert summary["correct"] == 1
    assert summary["wrong"] == 1
    assert summary["self_check"] == 1
    assert summary["mistakes"] == 1
    assert summary["latest_attempted_at"] is not None
