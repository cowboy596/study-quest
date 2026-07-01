# 变更日志

## V0.5

- 新增 Manage/管理页面，用于查看题库、筛选题目和查看学习状态。
- 新增 `attempts` 表，记录每次作答的答案、正确性、状态和时间。
- Quiz 提交后自动写入 attempts：客观题记录正确/错误，简答题记录自查。
- Manage 页面顶部显示题库总数、已做、未做、正确、错误、自查和错题集数量。
- Manage 页面支持按科目、题型、学习状态和题干关键词筛选。
- Manage 页面支持查看题目详情、编辑题目、删除题目。
- 删除题目时同步清理错题集、收藏夹和作答记录。
- Manage 页面支持加入错题集和移出错题集，保持错题去重。
- 新增学习状态和题库管理单元测试。

## V0.4

- Import 页面支持 CSV、XLSX、JSON、Markdown、TXT 多格式题库导入。
- 新增统一解析入口 `parse_questions_file()`。
- 导入流程改为先解析预览，用户确认后再保存到题库。
- 保存继续复用 `save_questions()` 去重逻辑。
- 新增解析统计：文件总题数、解析失败数量、错误明细。
- 支持 JSON 对象格式 `{"questions": [...]}` 和直接 question list。
- 支持 Markdown/TXT 固定模板，多题用 `---` 分隔。
- 新增 `examples/sample_questions.xlsx`、`.json`、`.md`、`.txt`。
- 新增多格式导入单元测试。

## V0.3

- AI Generate 页面从占位页升级为本地 Ollama 出题页面。
- 支持输入主题、题型、题目数量和难度后生成题目。
- 使用 Pydantic Schema 校验 AI 返回的结构化 JSON。
- AI 生成预览不显示答案和解析，保存后在 Quiz 中作答提交后再显示。
- 支持将 AI 生成题目以 `source = ai` 保存到本地题库。
- AI 题目保存复用现有去重逻辑，重复题会跳过。
- 增加 Ollama 服务不可用、模型缺失和响应校验失败的友好提示。
- 更新 `.env.example`，使用 `OLLAMA_BASE_URL` 和 `OLLAMA_MODEL`。

## V0.2

- 增加基于 Streamlit session state 的筛选随机刷题流程。
- 增加单选、多选、判断题和简答题作答控件。
- 增加客观题批改、解析展示和本次练习统计。
- 增加客观题答错自动加入错题集。
- 增加独立的手动收藏夹。
- 增加支持筛选和移出的错题集、收藏夹页面。
- 增加集合去重索引和完整单元测试。

## V0.1.1

- 增加 AI Generate、Quiz、Mistakes 占位页面。
- 增加 CSV 重复导入跳过逻辑。
- 增加导入结果统计。
- 增加清空题库按钮。
- 完善 Home 页面状态展示。

## V0.1

- 创建初始项目骨架。
- 创建 SQLite 数据库结构。
- 创建 `questions` 和 `mistakes` 表。
- 增加 CSV 题库导入流程。
- 增加示例 CSV。
- 增加基础 Streamlit 首页和导入页面。
