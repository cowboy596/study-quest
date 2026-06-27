from __future__ import annotations

import json

import streamlit as st

from modules.db import (
    DEFAULT_DB_PATH,
    clear_all_questions,
    count_matching_questions,
    count_mistakes,
    count_questions,
    get_random_questions,
    get_subjects,
    initialize_database,
)
from modules.grading import grade_answer
from modules.importer import ImportValidationError, import_questions_csv
from modules.mistakes import (
    add_favorite,
    add_mistake,
    count_favorites,
    list_favorites,
    list_mistakes,
    remove_favorite,
    remove_mistake,
)
from modules.quiz import (
    build_quiz_stats,
    format_answer_with_options,
    get_display_options,
    parse_options,
)

APP_VERSION = "V0.2"
NAVIGATION_ITEMS = [
    "Home",
    "Import CSV",
    "AI Generate",
    "Quiz",
    "Mistakes",
    "Favorites",
]
SUPPORTED_QUESTION_TYPES = [
    "single_choice",
    "multiple_choice",
    "true_false",
    "short_answer",
]


def main() -> None:
    st.set_page_config(page_title="StudyQuest", page_icon="SQ", layout="centered")
    initialize_database(DEFAULT_DB_PATH)

    st.title("StudyQuest")
    page = st.sidebar.radio("Navigation", NAVIGATION_ITEMS)

    if page == "Home":
        render_home()
    elif page == "Import CSV":
        render_import()
    elif page == "AI Generate":
        render_ai_generate()
    elif page == "Quiz":
        render_quiz()
    elif page == "Mistakes":
        render_mistakes()
    else:
        render_favorites()


def render_home() -> None:
    st.header("Home")
    st.write(f"StudyQuest current version: {APP_VERSION}")

    col_questions, col_mistakes, col_favorites = st.columns(3)
    col_questions.metric("Current question count", count_questions(DEFAULT_DB_PATH))
    col_mistakes.metric("Current mistake count", count_mistakes(DEFAULT_DB_PATH))
    col_favorites.metric("Current favorite count", count_favorites(DEFAULT_DB_PATH))

    st.subheader("Completed in V0.2")
    st.write("- CSV question-bank import with duplicate skipping")
    st.write("- Filtered random quizzes with session persistence")
    st.write("- Objective-question grading and explanations")
    st.write("- Automatic mistake collection and manual favorites")

    st.subheader("Next stage")
    st.write("V0.3: AI-assisted question generation. No AI API is connected yet.")


def render_import() -> None:
    st.header("Import Question Bank")
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    st.warning("Clear all questions will delete every question and mistake record.")
    confirm_clear = st.checkbox("I understand this will clear the question bank")
    if st.button("Clear all questions", disabled=not confirm_clear):
        clear_all_questions(DEFAULT_DB_PATH)
        st.success("Question bank, mistakes, and favorites have been cleared.")
        st.metric("Current question count", count_questions(DEFAULT_DB_PATH))

    if uploaded_file is None:
        st.info("Use examples/sample_questions.csv to test the importer.")
        return

    if st.button("Import"):
        try:
            imported_count = import_questions_csv(
                uploaded_file,
                DEFAULT_DB_PATH,
                source=uploaded_file.name,
            )
        except ImportValidationError as exc:
            st.error(str(exc))
        except Exception as exc:  # pragma: no cover - Streamlit surface guard
            st.error(f"Import failed: {exc}")
        else:
            st.success("Import finished.")
            st.write(f"Total rows in this file: {imported_count.total_rows}")
            st.write(f"New questions inserted: {imported_count.inserted_rows}")
            st.write(f"Duplicate questions skipped: {imported_count.skipped_duplicates}")
            st.metric("Current question count", count_questions(DEFAULT_DB_PATH))


def render_ai_generate() -> None:
    st.header("AI Generate")
    st.write("V0.3 will support generating question banks by topic.")


def render_quiz() -> None:
    st.header("Quiz")
    subjects = get_subjects(DEFAULT_DB_PATH)
    subject_choice = st.selectbox("Subject", ["All", *subjects])
    type_choice = st.selectbox("Type", ["All", *SUPPORTED_QUESTION_TYPES])
    question_count = int(
        st.number_input("Question count", min_value=1, value=5, step=1)
    )

    if st.button("Start Quiz", type="primary"):
        subject = None if subject_choice == "All" else subject_choice
        question_type = None if type_choice == "All" else type_choice
        available = count_matching_questions(
            DEFAULT_DB_PATH,
            subject=subject,
            question_type=question_type,
        )
        st.session_state.quiz_id = st.session_state.get("quiz_id", 0) + 1
        st.session_state.quiz_results = []
        st.session_state.quiz_submitted = False
        if available == 0:
            st.session_state.quiz_questions = []
            st.session_state.quiz_notice = "No matching questions are available."
        else:
            st.session_state.quiz_questions = get_random_questions(
                DEFAULT_DB_PATH,
                subject=subject,
                question_type=question_type,
                count=question_count,
            )
            st.session_state.quiz_notice = (
                f"Only {available} matching questions are available; "
                f"the quiz contains {available}."
                if available < question_count
                else ""
            )

    notice = st.session_state.get("quiz_notice", "")
    if notice:
        st.info(notice)

    questions = st.session_state.get("quiz_questions", [])
    if not questions:
        if count_questions(DEFAULT_DB_PATH) == 0:
            st.info("The question bank is empty. Import a CSV before starting a quiz.")
        return

    if not st.session_state.get("quiz_submitted", False):
        _render_quiz_form(questions)

    if st.session_state.get("quiz_submitted", False):
        _render_quiz_results(st.session_state.get("quiz_results", []))


def _render_quiz_form(questions: list[dict[str, object]]) -> None:
    answers: dict[int, object] = {}
    quiz_id = st.session_state.get("quiz_id", 0)
    with st.form("quiz_form"):
        for number, question in enumerate(questions, start=1):
            question_id = int(question["id"])
            question_type = str(question["type"])
            st.subheader(f"Question {number}")
            st.caption(f"{question['subject']} | {question_type}")
            st.write(str(question["stem"]))
            widget_key = f"quiz_answer_{quiz_id}_{question_id}"
            options = parse_options(str(question["options"]))

            if question_type == "single_choice":
                if options:
                    answers[question_id] = st.radio(
                        "Answer",
                        options,
                        index=None,
                        key=widget_key,
                    )
                else:
                    st.warning("This question has no valid options.")
                    answers[question_id] = None
            elif question_type == "multiple_choice":
                answers[question_id] = st.multiselect(
                    "Answer",
                    options,
                    key=widget_key,
                )
            elif question_type == "true_false":
                answers[question_id] = st.radio(
                    "Answer",
                    ["True", "False"],
                    index=None,
                    key=widget_key,
                )
            else:
                answers[question_id] = st.text_area("Answer", key=widget_key)

        submitted = st.form_submit_button("Submit Quiz", type="primary")

    if submitted:
        results: list[dict[str, object]] = []
        for question in questions:
            question_id = int(question["id"])
            user_answer = answers.get(question_id)
            status = grade_answer(
                str(question["type"]),
                user_answer,
                question["answer"],
            )
            result = {
                "question": question,
                "user_answer": user_answer,
                "status": status,
            }
            results.append(result)
            if status == "incorrect":
                add_mistake(
                    question_id,
                    _serialize_answer(user_answer),
                    str(question["answer"]),
                    DEFAULT_DB_PATH,
                )
        st.session_state.quiz_results = results
        st.session_state.quiz_submitted = True


def _serialize_answer(answer: object) -> str:
    if answer is None:
        return ""
    if isinstance(answer, list):
        return json.dumps(answer, ensure_ascii=False)
    return str(answer)


def _display_answer(answer: object) -> str:
    if answer is None or answer == "":
        return "No answer"
    if isinstance(answer, list):
        return ", ".join(str(item) for item in answer)
    return str(answer)


def _render_quiz_results(results: list[dict[str, object]]) -> None:
    st.subheader("Quiz Results")
    stats = build_quiz_stats(results)
    columns = st.columns(6)
    columns[0].metric("Total", stats["total"])
    columns[1].metric("Auto graded", stats["auto_graded"])
    columns[2].metric("Correct", stats["correct"])
    columns[3].metric("Incorrect", stats["incorrect"])
    columns[4].metric("Accuracy", f"{stats['accuracy']}%")
    columns[5].metric("Self check", stats["self_check"])

    for number, result in enumerate(results, start=1):
        question = result["question"]
        status = str(result["status"])
        st.subheader(f"Question {number}: {status.replace('_', ' ').title()}")
        st.write(str(question["stem"]))
        st.write(f"Your answer: {_display_answer(result['user_answer'])}")
        correct_answer = format_answer_with_options(
            question["answer"],
            parse_options(str(question["options"])),
        )
        st.write(f"Correct answer: {correct_answer}")
        if status == "self_check":
            st.info("Please compare your answer with the reference answer.")
        elif status == "correct":
            st.success("Correct")
        else:
            st.error("Incorrect - added to Mistakes")
        st.write(f"Explanation: {question['explanation'] or 'No explanation provided.'}")
        question_id = int(question["id"])
        if st.button("Add to Favorites", key=f"favorite_result_{question_id}"):
            if add_favorite(question_id, DEFAULT_DB_PATH):
                st.success("Added to Favorites.")
            else:
                st.info("This question is already in Favorites.")
        st.divider()


def render_mistakes() -> None:
    st.header("Mistakes")
    _render_collection("mistakes")


def render_favorites() -> None:
    st.header("Favorites")
    _render_collection("favorites")


def _render_collection(collection: str) -> None:
    subjects = get_subjects(DEFAULT_DB_PATH)
    subject_choice = st.selectbox(
        "Subject",
        ["All", *subjects],
        key=f"{collection}_subject",
    )
    subject = None if subject_choice == "All" else subject_choice
    rows = (
        list_mistakes(DEFAULT_DB_PATH, subject=subject)
        if collection == "mistakes"
        else list_favorites(DEFAULT_DB_PATH, subject=subject)
    )
    if not rows:
        st.info(f"No {collection} found.")
        return

    for row in rows:
        question_id = int(row["question_id"])
        with st.expander(str(row["stem"]), expanded=True):
            st.caption(f"{row['subject']} | {row['type']}")
            if collection == "mistakes":
                st.markdown("**Question**")
                st.write(str(row["stem"]))
                display_options = get_display_options(
                    str(row["type"]),
                    parse_options(str(row["options"])),
                )
                if display_options:
                    st.markdown("**Options**")
                    for option in display_options:
                        st.write(option)
                st.write(f"Your answer: {row['user_answer'] or 'No answer'}")
            correct_answer = format_answer_with_options(
                row["correct_answer"],
                parse_options(str(row["options"])),
            )
            st.write(f"Correct answer: {correct_answer}")
            st.write(f"Explanation: {row['explanation'] or 'No explanation provided.'}")
            st.write(f"Added at: {row['added_at']}")
            label = "Remove from Mistakes" if collection == "mistakes" else "Remove from Favorites"
            if st.button(label, key=f"remove_{collection}_{question_id}"):
                if collection == "mistakes":
                    remove_mistake(question_id, DEFAULT_DB_PATH)
                else:
                    remove_favorite(question_id, DEFAULT_DB_PATH)
                st.rerun()


if __name__ == "__main__":
    main()
