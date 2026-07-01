import json

from modules.analytics import (
    get_overall_stats,
    get_recent_attempts,
    get_review_recommendations,
    get_subject_stats,
    get_type_stats,
    get_weak_question_types,
    get_weak_subjects,
)
from modules.db import get_connection, initialize_database
from modules.mistakes import add_mistake
from modules.progress import record_attempt


def _question_ids(db_path):
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT id, stem FROM questions ORDER BY id").fetchall()
    return {row["stem"]: int(row["id"]) for row in rows}


def _seed_analytics_db(tmp_path):
    db_path = tmp_path / "analytics.db"
    initialize_database(db_path)
    questions = [
        ("Python", "single_choice", "Python easy?", ["A. Yes", "B. No"], "A"),
        ("Python", "multiple_choice", "Python multi?", ["A. One", "B. Two", "C. Three"], '["A", "C"]'),
        ("Networking", "true_false", "TCP reliable?", [], "True"),
        ("Networking", "single_choice", "UDP reliable?", ["A. Yes", "B. No"], "B"),
        ("Networking", "short_answer", "Explain TCP.", [], "Transport protocol"),
        ("Database", "single_choice", "SQL table?", ["A. Row", "B. Table"], "B"),
    ]
    with get_connection(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO questions (
                source, subject, type, stem, options, answer, explanation, tags, difficulty
            ) VALUES ('test', ?, ?, ?, ?, ?, 'Explanation', '', 'easy')
            """,
            [
                (subject, question_type, stem, json.dumps(options), answer)
                for subject, question_type, stem, options, answer in questions
            ],
        )
        conn.commit()
    ids = _question_ids(db_path)
    record_attempt(ids["Python easy?"], "A", True, "correct", db_path)
    record_attempt(ids["Python easy?"], "B", False, "wrong", db_path)
    record_attempt(ids["Python multi?"], '["A", "C"]', True, "correct", db_path)
    record_attempt(ids["TCP reliable?"], "False", False, "wrong", db_path)
    record_attempt(ids["UDP reliable?"], "B", True, "correct", db_path)
    record_attempt(ids["Explain TCP."], "TCP is transport.", None, "self_check", db_path)
    add_mistake(ids["Python easy?"], "B", "A", db_path)
    add_mistake(ids["TCP reliable?"], "False", "True", db_path)
    return db_path


def test_empty_database_dashboard_stats_do_not_crash(tmp_path):
    db_path = tmp_path / "empty.db"
    initialize_database(db_path)

    assert get_overall_stats(db_path) == {
        "total_questions": 0,
        "attempted_questions": 0,
        "unattempted_questions": 0,
        "total_attempts": 0,
        "objective_attempts": 0,
        "objective_correct": 0,
        "objective_wrong": 0,
        "objective_accuracy": 0.0,
        "mistakes": 0,
        "latest_attempted_at": None,
        "recent_7_day_attempts": 0,
    }
    assert get_subject_stats(db_path) == []
    assert get_type_stats(db_path) == []
    assert get_recent_attempts(db_path) == []


def test_overall_stats_count_questions_attempts_accuracy_and_self_check(tmp_path):
    db_path = _seed_analytics_db(tmp_path)

    stats = get_overall_stats(db_path)

    assert stats["total_questions"] == 6
    assert stats["attempted_questions"] == 5
    assert stats["unattempted_questions"] == 1
    assert stats["total_attempts"] == 6
    assert stats["objective_attempts"] == 5
    assert stats["objective_correct"] == 3
    assert stats["objective_wrong"] == 2
    assert stats["objective_accuracy"] == 60.0
    assert stats["mistakes"] == 2
    assert stats["latest_attempted_at"] is not None
    assert stats["recent_7_day_attempts"] == 6


def test_subject_stats_use_latest_attempt_status_and_mistakes(tmp_path):
    db_path = _seed_analytics_db(tmp_path)

    rows = {row["subject"]: row for row in get_subject_stats(db_path)}

    assert rows["Python"]["total_questions"] == 2
    assert rows["Python"]["attempted_questions"] == 2
    assert rows["Python"]["unattempted_questions"] == 0
    assert rows["Python"]["correct"] == 1
    assert rows["Python"]["wrong"] == 1
    assert rows["Python"]["accuracy"] == 50.0
    assert rows["Python"]["mistakes"] == 1
    assert rows["Python"]["latest_attempted_at"] is not None

    assert rows["Database"]["total_questions"] == 1
    assert rows["Database"]["attempted_questions"] == 0
    assert rows["Database"]["unattempted_questions"] == 1
    assert rows["Database"]["accuracy"] == 0.0


def test_type_stats_include_self_check_and_mistakes(tmp_path):
    db_path = _seed_analytics_db(tmp_path)

    rows = {row["type"]: row for row in get_type_stats(db_path)}

    assert rows["single_choice"]["total_questions"] == 3
    assert rows["single_choice"]["attempted_questions"] == 2
    assert rows["single_choice"]["unattempted_questions"] == 1
    assert rows["single_choice"]["correct"] == 1
    assert rows["single_choice"]["wrong"] == 1
    assert rows["single_choice"]["accuracy"] == 50.0
    assert rows["single_choice"]["mistakes"] == 1

    assert rows["short_answer"]["self_check"] == 1
    assert rows["short_answer"]["accuracy"] == 0.0


def test_weak_subjects_and_types_sort_by_accuracy_then_mistakes(tmp_path):
    db_path = _seed_analytics_db(tmp_path)

    weak_subjects = get_weak_subjects(db_path)
    weak_types = get_weak_question_types(db_path)

    assert [row["subject"] for row in weak_subjects] == ["Networking", "Python"]
    assert weak_subjects[0]["accuracy"] == 50.0
    assert [row["type"] for row in weak_types] == ["true_false", "single_choice", "multiple_choice"]
    assert "short_answer" not in [row["type"] for row in weak_types]


def test_recent_attempts_are_descending_and_include_question_data(tmp_path):
    db_path = _seed_analytics_db(tmp_path)

    rows = get_recent_attempts(db_path, limit=3)

    assert len(rows) == 3
    assert rows[0]["attempt_id"] > rows[1]["attempt_id"] > rows[2]["attempt_id"]
    assert rows[0]["stem_summary"]
    assert rows[0]["subject"]
    assert rows[0]["type"]
    assert "correct_answer" in rows[0]
    assert rows[0]["status"] in {"correct", "wrong", "self_check"}


def test_recommendations_include_mistakes_weak_items_unattempted_and_inactivity(tmp_path):
    db_path = _seed_analytics_db(tmp_path)

    recommendations = get_review_recommendations(db_path)

    assert any("优先复习错题集" in item for item in recommendations)
    assert any("薄弱主题" in item for item in recommendations)
    assert any("薄弱题型" in item for item in recommendations)
    assert any("未做题" in item for item in recommendations)

    empty_db = tmp_path / "empty_recommendations.db"
    initialize_database(empty_db)
    assert any("建议开始一次复习" in item for item in get_review_recommendations(empty_db))
