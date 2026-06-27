from modules.grading import grade_answer


def test_single_choice_grading_accepts_option_text_and_label():
    assert grade_answer("single_choice", "A. TCP", "A") == "correct"
    assert grade_answer("single_choice", "B. UDP", "A") == "incorrect"


def test_multiple_choice_grading_ignores_order_and_option_text():
    assert grade_answer(
        "multiple_choice",
        ["C. IP", "A. TCP"],
        '["A", "C"]',
    ) == "correct"
    assert grade_answer("multiple_choice", ["A"], '["A", "C"]') == "incorrect"


def test_true_false_grading_normalizes_supported_values():
    assert grade_answer("true_false", "正确", "True") == "correct"
    assert grade_answer("true_false", "错误", "True") == "incorrect"


def test_short_answer_is_self_check():
    assert grade_answer("short_answer", "My response", "Reference") == "self_check"


def test_unanswered_objective_question_is_incorrect():
    assert grade_answer("single_choice", None, "A") == "incorrect"
