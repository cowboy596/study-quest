# StudyQuest

StudyQuest 是一个本地个人刷题学习 Web 工具。当前版本 V0.5 支持 CSV、XLSX、JSON、Markdown、TXT 多格式题库导入，随机刷题、客观题批改、解析展示、错题集、收藏夹、题库管理、学习状态记录，以及基于本地 Ollama 的 AI 出题和保存。

## 安装依赖

```powershell
cd C:\Users\Admin\Documents\Codex\2026-06-26\studyquest-v0-1-web-ai-api\outputs\study-quest
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 启动项目

```powershell
python -m streamlit run app.py
```

默认访问地址通常是 `http://localhost:8501`。

## 多格式导入模板

CSV 和 XLSX 必须包含字段：

```text
subject,type,stem,options,answer,explanation,tags,difficulty
```

CSV/XLSX 中 `options` 使用 JSON 字符串：

```json
["A. TCP","B. UDP","C. IP","D. HTTP"]
```

JSON 支持两种格式：

```json
{
  "questions": [
    {
      "subject": "Networking",
      "type": "single_choice",
      "stem": "Which protocol is connection-oriented?",
      "options": ["A. TCP", "B. UDP", "C. IP", "D. HTTP"],
      "answer": "A",
      "explanation": "TCP establishes a connection before transferring data.",
      "tags": "network,protocol",
      "difficulty": "easy"
    }
  ]
}
```

也兼容直接传入 question list：

```json
[
  {
    "subject": "Networking",
    "type": "single_choice",
    "stem": "Which protocol is connection-oriented?",
    "options": ["A. TCP", "B. UDP"],
    "answer": "A",
    "explanation": "TCP establishes a connection before transferring data.",
    "tags": "network",
    "difficulty": "easy"
  }
]
```

Markdown 和 TXT 使用固定模板，多题用 `---` 分隔：

```text
---
subject: 计算机网络
type: single_choice
difficulty: medium
tags: TCP/IP
stem: TCP 协议属于哪一层？
options:
A. 应用层
B. 传输层
C. 网络层
D. 数据链路层
answer: B
explanation: TCP 是传输层协议，负责端到端可靠传输。
---
```

## 验证导入

1. 打开“导入题库”页面。
2. 上传 `examples/sample_questions.csv`、`.xlsx`、`.json`、`.md` 或 `.txt`。
3. 检查解析预览和错误明细。
4. 点击“保存到题库”。
5. 确认新增数量、重复跳过数量、解析失败数量和当前题库总数。
6. 再导入同一个文件，确认重复题被跳过。

## 验证刷题

1. 导入任意示例题库。
2. 打开“刷题”，按导入题目的 subject/type 筛选。
3. 点击“开始刷题”，确认题目可以被抽到。
4. 作答并提交，确认答案和解析只在提交后显示。
5. 使用“加入错题集”和“加入收藏夹”验证集合功能。

## 验证题库管理

1. 打开“管理”页面。
2. 查看顶部题库总数、已做题数、未做题数、正确数、错误数、自查数和错题集数量。
3. 使用“科目”“题型”“学习状态”和“题干关键词”筛选题目。
4. 展开题目查看完整题干、选项、答案、解析和最近作答状态。
5. 修改题目信息后点击“保存修改”，确认题目内容更新。
6. 勾选“确认删除这道题”后点击“删除题目”，确认题目、错题和作答记录同步清理。

## 配置本地 Ollama

AI Generate 使用本地 Ollama，不需要 API Key。

```powershell
ollama pull qwen3:8b
```

如需修改模型或服务地址，复制 `.env.example` 为 `.env` 后调整：

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
```

## 运行测试

当前环境如遇到全局 pytest 插件兼容问题，先禁用插件自动加载：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest -q
```

## V0.5 范围

已包含：

- SQLite 数据库初始化。
- CSV、XLSX、JSON、Markdown、TXT 多格式导入。
- 导入前预览和确认保存。
- 行级/题级错误明细。
- 重复题跳过。
- 随机抽题、答题、客观题批改和解析展示。
- 错题集与收藏夹。
- 本地 Ollama AI 出题。
- attempts 作答记录表。
- Quiz 提交后写入学习记录。
- 管理页查看、筛选、搜索、编辑、删除题目。
- 管理页显示未做、已做-正确、已做-错误、已做-自查状态。

未包含：

- PDF、Word、OCR。
- AI 自动解析非结构化文本。
- AI 批改简答题。
- 学习历史统计图表。
- 复习计划。
- 知识点掌握度分析。
- 登录注册。
- 复杂 UI。
