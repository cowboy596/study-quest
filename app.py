from __future__ import annotations

import json

import streamlit as st

from modules.analytics import (
    get_overall_stats,
    get_recent_attempts,
    get_review_recommendations,
    get_subject_stats,
    get_type_stats,
    get_weak_question_types,
    get_weak_subjects,
)
from modules.ai_generator import (
    AIGenerationError,
    AIModelMissingError,
    AIServiceUnavailableError,
    AIValidationError,
    generate_questions,
    get_ai_config,
)
from modules.db import (
    DEFAULT_DB_PATH,
    clear_all_questions,
    count_matching_questions,
    count_mistakes,
    count_questions,
    delete_question,
    get_connection,
    get_learning_summary,
    get_latest_attempt_status,
    get_questions_with_progress,
    get_random_questions,
    get_subjects,
    initialize_database,
    update_question,
)
from modules.grading import grade_answer
from modules.importer import ImportValidationError, parse_questions_file, save_questions
from modules.mistakes import (
    add_favorite,
    add_mistake,
    count_favorites,
    list_favorites,
    list_mistakes,
    remove_favorite,
    remove_mistake,
)
from modules.progress import record_attempt
from modules.quiz import (
    build_quiz_stats,
    format_answer_with_options,
    get_display_options,
    parse_options,
)
from modules.review import REVIEW_MODE_LABELS, count_review_questions, get_review_questions

APP_VERSION = "V0.7"
NAVIGATION_ITEMS = [
    "首页",
    "导入题库",
    "AI 出题",
    "刷题",
    "复习",
    "错题集",
    "管理",
    "Dashboard",
]
SUPPORTED_QUESTION_TYPES = [
    "single_choice",
    "multiple_choice",
    "true_false",
    "short_answer",
]
SUPPORTED_IMPORT_TYPES = ["csv", "xlsx", "json", "md", "txt"]
QUESTION_TYPE_LABELS = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "true_false": "判断题",
    "short_answer": "简答题",
}
DIFFICULTY_LABELS = {
    "easy": "简单",
    "medium": "中等",
    "hard": "困难",
}
BOOLEAN_ANSWER_OPTIONS = ["正确", "错误"]


def main() -> None:
    st.set_page_config(page_title="StudyQuest", page_icon="SQ", layout="centered")
    initialize_database(DEFAULT_DB_PATH)

    st.title("StudyQuest")
    page = st.sidebar.radio("导航", NAVIGATION_ITEMS)

    if page == "首页":
        render_home()
    elif page == "导入题库":
        render_import()
    elif page == "AI 出题":
        render_ai_generate()
    elif page == "刷题":
        render_quiz()
    elif page == "复习":
        render_review()
    elif page == "错题集":
        render_mistakes()
    elif page == "管理":
        render_manage()
    else:
        render_dashboard()


def render_home() -> None:
    st.header("首页")
    st.write(f"StudyQuest 当前版本：{APP_VERSION}")

    summary = get_learning_summary(DEFAULT_DB_PATH)
    overview_columns = st.columns(4)
    overview_columns[0].metric("题库总数", summary["total"])
    overview_columns[1].metric("已做题数", summary["attempted"])
    overview_columns[2].metric("未做题数", summary["unattempted"])
    overview_columns[3].metric("错题集数量", summary["mistakes"])
    status_columns = st.columns(4)
    status_columns[0].metric("正确题数", summary["correct"])
    status_columns[1].metric("错误题数", summary["wrong"])
    status_columns[2].metric("自查题数", summary["self_check"])
    status_columns[3].metric("最近一次练习时间", summary["latest_attempted_at"] or "暂无记录")

    st.subheader("V0.7 已完成功能")
    st.write("- CSV、XLSX、JSON、Markdown、TXT 多格式题库导入")
    st.write("- 导入预览、错误明细、重复题跳过")
    st.write("- 条件筛选随机刷题和会话保持")
    st.write("- 客观题批改、答案解析和练习统计")
    st.write("- 错题集与收藏夹")
    st.write("- 本地 Ollama AI 出题、预览和去重保存")
    st.write("- 题库管理、学习状态记录、题目编辑和删除")
    st.write("- 复习模式和薄弱项练习")
    st.write("- 学习统计、薄弱项分析和复习建议")

    st.subheader("下一阶段")
    st.write("V0.8：建议先完成 V0.7 验收后再确认范围。")


def render_import() -> None:
    st.header("导入题库")
    uploaded_file = st.file_uploader(
        "上传题库文件",
        type=SUPPORTED_IMPORT_TYPES,
    )

    st.warning("清空题库会删除所有题目、错题和收藏记录。")
    confirm_clear = st.checkbox("我确认要清空题库")
    if st.button("清空全部题目", disabled=not confirm_clear):
        clear_all_questions(DEFAULT_DB_PATH)
        st.success("题库、错题集和收藏夹已清空。")
        st.metric("当前题库数量", count_questions(DEFAULT_DB_PATH))

    if uploaded_file is None:
        st.info("可以使用项目 examples 目录中的示例文件测试导入。")
        return

    try:
        parsed = parse_questions_file(uploaded_file)
    except ImportValidationError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # pragma: no cover - Streamlit surface guard
        st.error(f"解析失败：{exc}")
        return

    st.write(f"文件题目总数：{parsed.total_rows}")
    st.write(f"解析失败数量：{parsed.failed_rows}")
    if parsed.errors:
        st.error("部分题目解析失败。")
        for error in parsed.errors:
            st.write(f"- {error}")

    if parsed.questions:
        st.subheader("预览")
        _render_import_preview(parsed.questions)
    else:
        st.warning("没有可导入的有效题目。")
        return

    if st.button("保存到题库", type="primary"):
        result = save_questions(
            parsed.questions,
            DEFAULT_DB_PATH,
            source=uploaded_file.name,
        )
        st.success("导入完成。")
        st.write(f"文件题目总数：{parsed.total_rows}")
        st.write(f"成功新增数量：{result.inserted_rows}")
        st.write(f"跳过重复数量：{result.skipped_duplicates}")
        st.write(f"解析失败数量：{parsed.failed_rows}")
        st.metric("当前题库数量", count_questions(DEFAULT_DB_PATH))


def _render_import_preview(questions: list[dict[str, object]]) -> None:
    for index, question in enumerate(questions, start=1):
        with st.expander(f"题目 {index}：{question['stem']}", expanded=index == 1):
            st.write(f"科目：{question['subject']}")
            st.write(f"题型：{_display_question_type(str(question['type']))}")
            st.write(f"题干：{question['stem']}")
            options = question.get("options", [])
            if options:
                st.write("选项：")
                for option in options:
                    st.write(f"- {option}")
            st.write(f"答案：{question['answer']}")
            st.write(f"解析：{question['explanation']}")
            st.write(f"标签：{question['tags']}")
            st.write(f"难度：{_display_difficulty(str(question['difficulty']))}")


def render_ai_generate() -> None:
    st.header("AI 出题")
    config = get_ai_config()
    st.caption(f"Ollama：{config.base_url} | 模型：{config.model}")
    st.info(
        "使用本地 Ollama。若生成失败，请确认已安装并启动 Ollama，"
        f"并已执行：ollama pull {config.model}"
    )

    subject = st.text_input("科目 / 主题", placeholder="计算机网络 TCP/IP")
    question_type = st.selectbox(
        "题型",
        SUPPORTED_QUESTION_TYPES,
        format_func=_display_question_type,
    )
    question_count = int(
        st.number_input("生成数量", min_value=1, max_value=20, value=5, step=1)
    )
    difficulty = st.selectbox(
        "难度",
        ["easy", "medium", "hard"],
        index=1,
        format_func=_display_difficulty,
    )

    if st.button("生成题目", type="primary"):
        if not subject.strip():
            st.error("请填写科目或主题。")
        else:
            try:
                generated = generate_questions(
                    subject=subject.strip(),
                    question_type=question_type,
                    question_count=question_count,
                    difficulty=difficulty,
                    config=config,
                )
            except AIModelMissingError as exc:
                st.error(str(exc))
            except AIServiceUnavailableError as exc:
                st.error(str(exc))
            except AIValidationError as exc:
                st.error(str(exc))
            except AIGenerationError as exc:
                st.error(str(exc))
            except Exception as exc:  # pragma: no cover - Streamlit surface guard
                st.error(f"AI 生成失败：{exc}")
            else:
                st.session_state.ai_generated_questions = generated
                st.success(f"已生成 {len(generated)} 道有效题目。")
                if len(generated) < question_count:
                    st.warning(
                        f"请求生成 {question_count} 道题，但只返回了 "
                        f"{len(generated)} 道有效题目。"
                    )

    generated_questions = st.session_state.get("ai_generated_questions", [])
    if not generated_questions:
        return

    st.subheader("预览")
    _render_generated_questions_preview(generated_questions)

    if st.button("保存到题库"):
        result = save_questions(generated_questions, DEFAULT_DB_PATH, source="ai")
        st.success("保存完成。")
        st.write(f"生成题目数量：{result.total_rows}")
        st.write(f"成功保存数量：{result.inserted_rows}")
        st.write(f"跳过重复数量：{result.skipped_duplicates}")
        st.metric("当前题库数量", count_questions(DEFAULT_DB_PATH))


def _render_generated_questions_preview(questions: list[dict[str, object]]) -> None:
    for index, question in enumerate(questions, start=1):
        with st.expander(f"题目 {index}：{question['stem']}", expanded=True):
            for label, value in _generated_question_preview_items(question):
                if label == "选项" and isinstance(value, list):
                    st.write("选项：")
                    for option in value:
                        st.write(f"- {option}")
                else:
                    st.write(f"{label}：{value}")


def _generated_question_preview_items(
    question: dict[str, object],
) -> list[tuple[str, object]]:
    items: list[tuple[str, object]] = [
        ("科目", question["subject"]),
        ("题型", _display_question_type(str(question["type"]))),
        ("难度", _display_difficulty(str(question["difficulty"]))),
        ("题干", question["stem"]),
    ]
    options = question.get("options", [])
    if options:
        items.append(("选项", options))
    items.append(("标签", question["tags"]))
    return items


def render_quiz() -> None:
    st.header("刷题")
    subjects = get_subjects(DEFAULT_DB_PATH)
    subject_choice = st.selectbox("科目", ["全部", *subjects])
    type_choice = st.selectbox(
        "题型",
        ["全部", *SUPPORTED_QUESTION_TYPES],
        format_func=lambda value: "全部" if value == "全部" else _display_question_type(value),
    )
    question_count = int(
        st.number_input("抽题数量", min_value=1, value=5, step=1)
    )

    if st.button("开始刷题", type="primary"):
        subject = None if subject_choice == "全部" else subject_choice
        question_type = None if type_choice == "全部" else type_choice
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
            st.session_state.quiz_notice = "没有符合条件的题目。"
        else:
            st.session_state.quiz_questions = get_random_questions(
                DEFAULT_DB_PATH,
                subject=subject,
                question_type=question_type,
                count=question_count,
            )
            st.session_state.quiz_notice = (
                f"当前只有 {available} 道符合条件的题目，本次练习将使用全部可用题目。"
                if available < question_count
                else ""
            )

    notice = st.session_state.get("quiz_notice", "")
    if notice:
        st.info(notice)

    questions = st.session_state.get("quiz_questions", [])
    if not questions:
        if count_questions(DEFAULT_DB_PATH) == 0:
            st.info("题库为空，请先导入题库文件。")
        return

    if not st.session_state.get("quiz_submitted", False):
        _render_quiz_form(questions)

    if st.session_state.get("quiz_submitted", False):
        _render_quiz_results(st.session_state.get("quiz_results", []))


def render_review() -> None:
    st.header("复习")
    mode_values = list(REVIEW_MODE_LABELS.keys())
    mode_choice = st.selectbox(
        "复习模式",
        mode_values,
        format_func=lambda value: REVIEW_MODE_LABELS[value],
    )
    subjects = get_subjects(DEFAULT_DB_PATH)
    subject_choice = st.selectbox("科目", ["全部", *subjects], key="review_subject")
    type_choice = st.selectbox(
        "题型",
        ["全部", *SUPPORTED_QUESTION_TYPES],
        key="review_type",
        format_func=lambda value: "全部" if value == "全部" else _display_question_type(value),
    )
    question_count = int(st.number_input("复习题数", min_value=1, value=5, step=1))

    if st.button("开始复习", type="primary"):
        subject = None if subject_choice == "全部" else subject_choice
        question_type = None if type_choice == "全部" else type_choice
        available = count_review_questions(
            DEFAULT_DB_PATH,
            mode_choice,
            subject=subject,
            question_type=question_type,
        )
        st.session_state.review_id = st.session_state.get("review_id", 0) + 1
        st.session_state.review_results = []
        st.session_state.review_submitted = False
        if available == 0:
            st.session_state.review_questions = []
            st.session_state.review_notice = "没有符合条件的复习题。"
        else:
            st.session_state.review_questions = get_review_questions(
                DEFAULT_DB_PATH,
                mode_choice,
                subject=subject,
                question_type=question_type,
                count=question_count,
            )
            st.session_state.review_notice = (
                f"当前只有 {available} 道符合条件的题目，本轮复习将使用全部可用题目。"
                if available < question_count
                else ""
            )

    notice = st.session_state.get("review_notice", "")
    if notice:
        st.info(notice)

    questions = st.session_state.get("review_questions", [])
    if not questions:
        if count_questions(DEFAULT_DB_PATH) == 0:
            st.info("题库为空，请先导入题库文件。")
        return

    if not st.session_state.get("review_submitted", False):
        _render_review_form(questions)

    if st.session_state.get("review_submitted", False):
        _render_review_results(st.session_state.get("review_results", []))


def _render_quiz_form(questions: list[dict[str, object]]) -> None:
    answers: dict[int, object] = {}
    quiz_id = st.session_state.get("quiz_id", 0)
    with st.form("quiz_form"):
        for number, question in enumerate(questions, start=1):
            question_id = int(question["id"])
            question_type = str(question["type"])
            st.subheader(f"题目 {number}")
            st.caption(f"{question['subject']} | {_display_question_type(question_type)}")
            st.write(str(question["stem"]))
            widget_key = f"quiz_answer_{quiz_id}_{question_id}"
            options = parse_options(str(question["options"]))

            if question_type == "single_choice":
                if options:
                    answers[question_id] = st.radio(
                        "答案",
                        options,
                        index=None,
                        key=widget_key,
                    )
                else:
                    st.warning("这道题没有有效选项。")
                    answers[question_id] = None
            elif question_type == "multiple_choice":
                answers[question_id] = st.multiselect(
                    "答案",
                    options,
                    key=widget_key,
                )
            elif question_type == "true_false":
                answers[question_id] = st.radio(
                    "答案",
                    BOOLEAN_ANSWER_OPTIONS,
                    index=None,
                    key=widget_key,
                )
            else:
                answers[question_id] = st.text_area("答案", key=widget_key)

        submitted = st.form_submit_button("提交练习", type="primary")

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
            stored_user_answer = _serialize_answer(user_answer)
            attempt_status = _attempt_status(status)
            record_attempt(
                question_id,
                stored_user_answer,
                _attempt_is_correct(attempt_status),
                attempt_status,
                DEFAULT_DB_PATH,
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
                    stored_user_answer,
                    str(question["answer"]),
                    DEFAULT_DB_PATH,
                )
        st.session_state.quiz_results = results
        st.session_state.quiz_submitted = True


def _render_review_form(questions: list[dict[str, object]]) -> None:
    answers: dict[int, object] = {}
    review_id = st.session_state.get("review_id", 0)
    with st.form("review_form"):
        for number, question in enumerate(questions, start=1):
            question_id = int(question["id"])
            question_type = str(question["type"])
            st.subheader(f"题目 {number}")
            st.caption(f"{question['subject']} | {_display_question_type(question_type)}")
            st.write(str(question["stem"]))
            st.write(f"当前学习状态：{question.get('learning_status', '未做')}")
            widget_key = f"review_answer_{review_id}_{question_id}"
            options = parse_options(str(question["options"]))

            if question_type == "single_choice":
                if options:
                    answers[question_id] = st.radio("答案", options, index=None, key=widget_key)
                else:
                    st.warning("这道题没有有效选项。")
                    answers[question_id] = None
            elif question_type == "multiple_choice":
                answers[question_id] = st.multiselect("答案", options, key=widget_key)
            elif question_type == "true_false":
                answers[question_id] = st.radio("答案", BOOLEAN_ANSWER_OPTIONS, index=None, key=widget_key)
            else:
                answers[question_id] = st.text_area("答案", key=widget_key)

        submitted = st.form_submit_button("提交复习", type="primary")

    if submitted:
        st.session_state.review_results = [
            _submit_review_answer(question, answers.get(int(question["id"])), DEFAULT_DB_PATH)
            for question in questions
        ]
        st.session_state.review_submitted = True


def _submit_review_answer(
    question: dict[str, object],
    user_answer: object,
    db_path=DEFAULT_DB_PATH,
) -> dict[str, object]:
    question_id = int(question["id"])
    previous_status = get_latest_attempt_status(question_id, db_path)
    was_in_mistakes = _question_in_mistakes(question_id, db_path)
    status = grade_answer(str(question["type"]), user_answer, question["answer"])
    stored_user_answer = _serialize_answer(user_answer)
    attempt_status = _attempt_status(status)
    record_attempt(
        question_id,
        stored_user_answer,
        _attempt_is_correct(attempt_status),
        attempt_status,
        db_path,
    )
    if status == "incorrect":
        add_mistake(question_id, stored_user_answer, str(question["answer"]), db_path)
    return {
        "question": question,
        "user_answer": user_answer,
        "status": status,
        "previous_status": previous_status,
        "current_status": attempt_status,
        "was_in_mistakes": was_in_mistakes,
    }


def _remove_review_mistake(question_id: int, db_path=DEFAULT_DB_PATH) -> None:
    remove_mistake(question_id, db_path)


def _question_in_mistakes(question_id: int, db_path=DEFAULT_DB_PATH) -> bool:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM mistakes WHERE question_id = ?",
            (question_id,),
        ).fetchone()
    return row is not None


def _serialize_answer(answer: object) -> str:
    if answer is None:
        return ""
    if isinstance(answer, list):
        return json.dumps(answer, ensure_ascii=False)
    return str(answer)


def _display_answer(answer: object) -> str:
    if answer is None or answer == "":
        return "未作答"
    if isinstance(answer, list):
        return ", ".join(str(item) for item in answer)
    if str(answer) == "True":
        return "正确"
    if str(answer) == "False":
        return "错误"
    return str(answer)


def _render_quiz_results(results: list[dict[str, object]]) -> None:
    st.subheader("练习结果")
    stats = build_quiz_stats(results)
    columns = st.columns(6)
    columns[0].metric("总题数", stats["total"])
    columns[1].metric("自动批改", stats["auto_graded"])
    columns[2].metric("正确", stats["correct"])
    columns[3].metric("错误", stats["incorrect"])
    columns[4].metric("正确率", f"{stats['accuracy']}%")
    columns[5].metric("自查题", stats["self_check"])

    for number, result in enumerate(results, start=1):
        question = result["question"]
        status = str(result["status"])
        st.subheader(f"题目 {number}：{_display_status(status)}")
        st.write(str(question["stem"]))
        st.write(f"你的答案：{_display_answer(result['user_answer'])}")
        correct_answer = _display_correct_answer(question)
        st.write(f"正确答案：{correct_answer}")
        if status == "self_check":
            st.info("请对照参考答案自查。")
        elif status == "correct":
            st.success("回答正确")
        else:
            st.error("回答错误，已自动加入错题集")
        st.write(f"解析：{question['explanation'] or '暂无解析。'}")
        question_id = int(question["id"])
        _render_quiz_result_collection_actions(question, result["user_answer"])
        st.divider()


def _render_review_results(results: list[dict[str, object]]) -> None:
    st.subheader("复习结果")
    stats = build_quiz_stats(results)
    columns = st.columns(6)
    columns[0].metric("总题数", stats["total"])
    columns[1].metric("自动批改", stats["auto_graded"])
    columns[2].metric("正确", stats["correct"])
    columns[3].metric("错误", stats["incorrect"])
    columns[4].metric("正确率", f"{stats['accuracy']}%")
    columns[5].metric("自查题", stats["self_check"])

    for number, result in enumerate(results, start=1):
        question = result["question"]
        status = str(result["status"])
        question_id = int(question["id"])
        st.subheader(f"题目 {number}：{_display_status(status)}")
        st.write(str(question["stem"]))
        st.write(f"你的答案：{_display_answer(result['user_answer'])}")
        st.write(f"正确答案：{_display_correct_answer(question)}")
        st.write(
            "本题学习状态变化："
            f"{_display_attempt_status(result.get('previous_status'))} -> "
            f"{_display_attempt_status(result.get('current_status'))}"
        )
        if status == "self_check":
            st.info("请对照参考答案自查。")
        elif status == "correct":
            st.success("回答正确")
            if result.get("was_in_mistakes"):
                if st.button("移出错题集", key=f"review_remove_mistake_{question_id}"):
                    _remove_review_mistake(question_id, DEFAULT_DB_PATH)
                    st.success("已移出错题集。")
                    st.rerun()
        else:
            st.error("回答错误，已自动加入错题集")
        st.write(f"解析：{question['explanation'] or '暂无解析。'}")
        st.divider()


def _display_status(status: str) -> str:
    return {
        "correct": "正确",
        "incorrect": "错误",
        "wrong": "错误",
        "self_check": "自查",
    }.get(status, status)


def _display_attempt_status(status: object) -> str:
    return {
        None: "未做",
        "correct": "已做-正确",
        "wrong": "已做-错误",
        "self_check": "已做-自查",
    }.get(status, str(status))


def _attempt_status(grading_status: str) -> str:
    return "wrong" if grading_status == "incorrect" else grading_status


def _attempt_is_correct(attempt_status: str) -> bool | None:
    if attempt_status == "correct":
        return True
    if attempt_status == "wrong":
        return False
    return None


def _display_question_type(question_type: str) -> str:
    return QUESTION_TYPE_LABELS.get(question_type, question_type)


def _display_difficulty(difficulty: str) -> str:
    return DIFFICULTY_LABELS.get(difficulty, difficulty)


def _display_correct_answer(question: dict[str, object]) -> str:
    if str(question["type"]) == "true_false":
        return _display_answer(question["answer"])
    return format_answer_with_options(
        question["answer"],
        parse_options(str(question["options"])),
    )


def _quiz_result_collection_action_labels() -> list[str]:
    return ["加入错题集", "加入收藏夹"]


def _render_quiz_result_collection_actions(
    question: dict[str, object],
    user_answer: object,
) -> None:
    question_id = int(question["id"])
    if st.button("加入错题集", key=f"mistake_result_{question_id}"):
        if add_mistake(
            question_id,
            _serialize_answer(user_answer),
            str(question["answer"]),
            DEFAULT_DB_PATH,
        ):
            st.success("已加入错题集。")
        else:
            st.info("这道题已经在错题集中。")
    if st.button("加入收藏夹", key=f"favorite_result_{question_id}"):
        if add_favorite(question_id, DEFAULT_DB_PATH):
            st.success("已加入收藏夹。")
        else:
            st.info("这道题已经在收藏夹中。")


def render_mistakes() -> None:
    st.header("错题集")
    _render_collection("mistakes")


def render_favorites() -> None:
    st.header("收藏夹")
    _render_collection("favorites")


def render_manage() -> None:
    st.header("题库管理")
    summary = get_learning_summary(DEFAULT_DB_PATH)
    columns = st.columns(7)
    columns[0].metric("题库总数", summary["total"])
    columns[1].metric("已做题数", summary["attempted"])
    columns[2].metric("未做题数", summary["unattempted"])
    columns[3].metric("已做正确数", summary["correct"])
    columns[4].metric("已做错误数", summary["wrong"])
    columns[5].metric("简答自查数", summary["self_check"])
    columns[6].metric("错题集数量", summary["mistakes"])

    subjects = get_subjects(DEFAULT_DB_PATH)
    subject_choice = st.selectbox("科目", ["全部", *subjects], key="manage_subject")
    type_choice = st.selectbox(
        "题型",
        ["全部", *SUPPORTED_QUESTION_TYPES],
        key="manage_type",
        format_func=lambda value: "全部" if value == "全部" else _display_question_type(value),
    )
    status_choice = st.selectbox(
        "学习状态",
        ["全部", "未做", "已做", "已做-正确", "已做-错误", "已做-自查"],
        key="manage_status",
    )
    keyword = st.text_input("题干关键词", key="manage_keyword")

    rows = get_questions_with_progress(
        DEFAULT_DB_PATH,
        subject=None if subject_choice == "全部" else subject_choice,
        question_type=None if type_choice == "全部" else type_choice,
        learning_status=None if status_choice == "全部" else status_choice,
        keyword=keyword.strip() or None,
    )
    if not rows:
        st.info("没有符合条件的题目。")
        return

    st.write(f"当前列表题目数：{len(rows)}")
    for row in rows:
        _render_manage_question(row)


def render_dashboard() -> None:
    st.header("Dashboard")

    overall = get_overall_stats(DEFAULT_DB_PATH)
    st.subheader("总体学习概览")
    overview_columns = st.columns(4)
    overview_columns[0].metric("题库总数", overall["total_questions"])
    overview_columns[1].metric("已做题数", overall["attempted_questions"])
    overview_columns[2].metric("未做题数", overall["unattempted_questions"])
    overview_columns[3].metric("总作答次数", overall["total_attempts"])
    objective_columns = st.columns(4)
    objective_columns[0].metric("客观题正确率", f"{overall['objective_accuracy']}%")
    objective_columns[1].metric("错题集数量", overall["mistakes"])
    objective_columns[2].metric("最近一次练习时间", overall["latest_attempted_at"] or "暂无记录")
    objective_columns[3].metric("最近 7 天练习次数", overall["recent_7_day_attempts"])

    st.subheader("按主题统计")
    subject_rows = get_subject_stats(DEFAULT_DB_PATH)
    if subject_rows:
        st.dataframe(subject_rows, use_container_width=True)
    else:
        st.info("暂无主题统计。")

    st.subheader("按题型统计")
    type_rows = get_type_stats(DEFAULT_DB_PATH)
    if type_rows:
        st.dataframe(type_rows, use_container_width=True)
    else:
        st.info("暂无题型统计。")

    st.subheader("薄弱项排行")
    weak_subjects = get_weak_subjects(DEFAULT_DB_PATH)
    weak_types = get_weak_question_types(DEFAULT_DB_PATH)
    if weak_subjects:
        st.markdown("**薄弱主题排行**")
        st.dataframe(weak_subjects, use_container_width=True)
    else:
        st.info("暂无可排行的薄弱主题。")
    if weak_types:
        st.markdown("**薄弱题型排行**")
        st.dataframe(weak_types, use_container_width=True)
    else:
        st.info("暂无可排行的薄弱题型。")

    st.subheader("最近作答记录")
    recent_attempts = get_recent_attempts(DEFAULT_DB_PATH)
    if recent_attempts:
        st.dataframe(recent_attempts, use_container_width=True)
    else:
        st.info("暂无作答记录。")

    st.subheader("推荐复习方向")
    for recommendation in get_review_recommendations(DEFAULT_DB_PATH):
        st.write(f"- {recommendation}")


def _render_manage_question(row: dict[str, object]) -> None:
    question_id = int(row["id"])
    stem = str(row["stem"])
    summary = stem if len(stem) <= 60 else f"{stem[:60]}..."
    mistake_text = "是" if int(row["in_mistakes"]) else "否"
    title = f"#{question_id} | {row['subject']} | {_display_question_type(str(row['type']))} | {row['learning_status']} | {summary}"
    with st.expander(title):
        st.write(f"题目 ID：{question_id}")
        st.write(f"科目：{row['subject']}")
        st.write(f"题型：{_display_question_type(str(row['type']))}")
        st.write(f"难度：{_display_difficulty(str(row['difficulty']))}")
        st.write(f"标签：{row['tags']}")
        st.write(f"学习状态：{row['learning_status']}")
        st.write(f"最近作答时间：{row['latest_attempted_at'] or '无'}")
        st.write(f"是否在错题集：{mistake_text}")
        st.markdown("**题目详情**")
        st.write(stem)
        display_options = get_display_options(
            str(row["type"]),
            parse_options(str(row["options"])),
        )
        if display_options:
            st.markdown("**选项**")
            for option in display_options:
                st.write(option)
        st.write(f"正确答案：{_display_correct_answer(row)}")
        st.write(f"解析：{row['explanation'] or '暂无解析。'}")

        _render_manage_mistake_actions(question_id, row)
        _render_manage_edit_form(question_id, row)
        _render_manage_delete_action(question_id)


def _render_manage_mistake_actions(question_id: int, row: dict[str, object]) -> None:
    if int(row["in_mistakes"]):
        if st.button("移出错题集", key=f"manage_remove_mistake_{question_id}"):
            remove_mistake(question_id, DEFAULT_DB_PATH)
            st.success("已移出错题集。")
            st.rerun()
    else:
        if st.button("加入错题集", key=f"manage_add_mistake_{question_id}"):
            if add_mistake(
                question_id,
                str(row.get("latest_user_answer") or ""),
                str(row["answer"]),
                DEFAULT_DB_PATH,
            ):
                st.success("已加入错题集。")
            else:
                st.info("这道题已经在错题集中。")
            st.rerun()


def _render_manage_edit_form(question_id: int, row: dict[str, object]) -> None:
    with st.form(f"manage_edit_{question_id}"):
        st.markdown("**编辑题目**")
        subject = st.text_input("科目", value=str(row["subject"]), key=f"edit_subject_{question_id}")
        question_type = st.selectbox(
            "题型",
            SUPPORTED_QUESTION_TYPES,
            index=SUPPORTED_QUESTION_TYPES.index(str(row["type"])),
            key=f"edit_type_{question_id}",
            format_func=_display_question_type,
        )
        stem = st.text_area("题干", value=str(row["stem"]), key=f"edit_stem_{question_id}")
        options = st.text_area("选项 JSON", value=str(row["options"]), key=f"edit_options_{question_id}")
        answer = st.text_input("答案", value=str(row["answer"]), key=f"edit_answer_{question_id}")
        explanation = st.text_area("解析", value=str(row["explanation"]), key=f"edit_explanation_{question_id}")
        tags = st.text_input("标签", value=str(row["tags"]), key=f"edit_tags_{question_id}")
        difficulty_values = ["easy", "medium", "hard"]
        current_difficulty = str(row["difficulty"])
        difficulty = st.selectbox(
            "难度",
            difficulty_values,
            index=difficulty_values.index(current_difficulty) if current_difficulty in difficulty_values else 0,
            key=f"edit_difficulty_{question_id}",
            format_func=_display_difficulty,
        )
        submitted = st.form_submit_button("保存修改")

    if submitted:
        try:
            update_question(
                question_id,
                {
                    "subject": subject,
                    "type": question_type,
                    "stem": stem,
                    "options": options,
                    "answer": answer,
                    "explanation": explanation,
                    "tags": tags,
                    "difficulty": difficulty,
                },
                DEFAULT_DB_PATH,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success("题目已更新。")
            st.rerun()


def _render_manage_delete_action(question_id: int) -> None:
    st.warning("删除题目会同时清理错题集、收藏夹和作答记录。")
    confirm = st.checkbox("确认删除这道题", key=f"confirm_delete_{question_id}")
    if st.button("删除题目", key=f"delete_question_{question_id}", disabled=not confirm):
        delete_question(question_id, DEFAULT_DB_PATH)
        st.success("题目已删除。")
        st.rerun()


def _render_collection(collection: str) -> None:
    subjects = get_subjects(DEFAULT_DB_PATH)
    subject_choice = st.selectbox(
        "科目",
        ["全部", *subjects],
        key=f"{collection}_subject",
    )
    subject = None if subject_choice == "全部" else subject_choice
    rows = (
        list_mistakes(DEFAULT_DB_PATH, subject=subject)
        if collection == "mistakes"
        else list_favorites(DEFAULT_DB_PATH, subject=subject)
    )
    if not rows:
        st.info("暂无错题。" if collection == "mistakes" else "暂无收藏。")
        return

    for row in rows:
        question_id = int(row["question_id"])
        with st.expander(str(row["stem"]), expanded=True):
            st.caption(f"{row['subject']} | {_display_question_type(str(row['type']))}")
            if collection == "mistakes":
                st.markdown("**题目**")
                st.write(str(row["stem"]))
                display_options = get_display_options(
                    str(row["type"]),
                    parse_options(str(row["options"])),
                )
                if display_options:
                    st.markdown("**选项**")
                    for option in display_options:
                        st.write(option)
                st.write(f"你的答案：{_display_answer(row['user_answer'])}")
            correct_answer = (
                _display_answer(row["correct_answer"])
                if str(row["type"]) == "true_false"
                else format_answer_with_options(
                    row["correct_answer"],
                    parse_options(str(row["options"])),
                )
            )
            st.write(f"正确答案：{correct_answer}")
            st.write(f"解析：{row['explanation'] or '暂无解析。'}")
            st.write(f"加入时间：{row['added_at']}")
            label = "移出错题集" if collection == "mistakes" else "移出收藏夹"
            if st.button(label, key=f"remove_{collection}_{question_id}"):
                if collection == "mistakes":
                    remove_mistake(question_id, DEFAULT_DB_PATH)
                else:
                    remove_favorite(question_id, DEFAULT_DB_PATH)
                st.rerun()


if __name__ == "__main__":
    main()
