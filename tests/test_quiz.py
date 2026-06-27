from modules.db import (
    count_matching_questions,
    get_question_types,
    get_random_questions,
    get_subjects,
)
from modules.quiz import (
    build_quiz_stats,
    format_answer_with_options,
    get_display_options,
    parse_options,
)


def test_random_questions_respect_count_and_filters(seeded_db):
    rows = get_random_questions(
        seeded_db,
        subject="Python",
        question_type="single_choice",
        count=2,
    )

    assert len(rows) == 2
    assert all(row["subject"] == "Python" for row in rows)
    assert all(row["type"] == "single_choice" for row in rows)


def test_random_questions_return_all_available_when_count_is_too_large(seeded_db):
    rows = get_random_questions(
        seeded_db,
        subject="Networking",
        question_type=None,
        count=10,
    )

    assert len(rows) == 2
    assert count_matching_questions(seeded_db, subject="Networking") == 2


def test_question_filter_values_are_distinct_and_sorted(seeded_db):
    assert get_subjects(seeded_db) == ["Networking", "Python"]
    assert get_question_types(seeded_db) == [
        "multiple_choice",
        "short_answer",
        "single_choice",
        "true_false",
    ]


def test_parse_options_returns_list_or_empty_list():
    assert parse_options('["A. TCP", "B. UDP"]') == ["A. TCP", "B. UDP"]
    assert parse_options("not-json") == []


def test_quiz_stats_exclude_self_check_from_accuracy():
    stats = build_quiz_stats(
        [
            {"status": "correct"},
            {"status": "incorrect"},
            {"status": "self_check"},
        ]
    )

    assert stats == {
        "total": 3,
        "auto_graded": 2,
        "correct": 1,
        "incorrect": 1,
        "accuracy": 50.0,
        "self_check": 1,
    }


def test_correct_single_choice_answer_includes_option_text():
    assert format_answer_with_options(
        "A",
        ["A. TCP", "B. UDP"],
    ) == "A. TCP"


def test_correct_multiple_choice_answer_includes_each_option_text():
    assert format_answer_with_options(
        '["A", "C"]',
        ["A. TCP", "B. UDP", "C. IP"],
    ) == "A. TCP, C. IP"


def test_true_false_answer_is_displayed_without_option_mapping():
    assert format_answer_with_options("True", []) == "True"


def test_choice_question_displays_all_stored_options():
    options = ["A. TCP", "B. UDP"]

    assert get_display_options("single_choice", options) == options


def test_true_false_question_displays_boolean_options():
    assert get_display_options("true_false", []) == ["True", "False"]


def test_short_answer_question_omits_options():
    assert get_display_options("short_answer", []) == []
