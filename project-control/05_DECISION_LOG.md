# Decision Log

## 2026-06-26

- Use SQLite directly through `sqlite3` for V0.1 to keep setup local and simple.
- Use Streamlit sidebar navigation instead of a full routing framework.
- Store `options` as a JSON string in the database for simple CSV compatibility.
- Reserve python-dotenv without loading real API credentials in V0.1.
- For V0.1.1, skip duplicate questions using `subject + type + stem + answer` instead of comparing every field, so explanations and tags can be corrected later without multiplying the same question.

## 2026-06-27

- Keep grading rules in a pure module so objective-question behavior is testable without Streamlit.
- Store active quizzes and submitted results in Streamlit session state.
- Automatically add only incorrect objective questions to Mistakes; short answers remain self-check in V0.2.
- Send all manual save actions to a separate Favorites collection so mistakes retain their diagnostic meaning.
- Enforce one Mistakes and one Favorites row per question with unique SQLite indexes.

## 2026-06-28

- V0.3 使用本地 Ollama 和 `qwen3:8b` 生成题目，不采用按请求计费的云端 API。
- 从本次设计开始，StudyQuest 新增或更新的项目文档默认使用中文；代码标识符、命令、环境变量和文件名保留其原始英文形式。
