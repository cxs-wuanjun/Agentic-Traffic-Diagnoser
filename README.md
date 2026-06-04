# Agentic-Traffic-Diagnoser 🚦

> **An Intelligent Traffic Diagnosis Agent driven by ReAct, RAG, and `agentskills.io` standard.**
> 
> 基于大语言模型（LLM）的自动化交通研判专家。具备实时交通查询、历史拥堵数据分析（Text2SQL）、合规预案问答（RAG），并能基于真正的 Agent Skills 规范自主编写代码，一键生成企业级红头分析报告。

---

## 🌟 核心特性 (Core Features)

- 🧠 **原生 ReAct 智能体架构**：抛弃预设工作流，大模型根据用户意图自主调度高德 API、SQL 库和 RAG 知识库。
- 📊 **真实数据驱动 (Data-Driven Text2SQL)**：将自然语言转化为 SQL，从本地 SQLite 历史库中提取精确的交通流量与车速数据，告别 LLM 的数据幻觉。
- 🔍 **高阶 RAG (LLM-as-a-Reranker)**：在处理交通处置标准预案时，采用“向量粗排 + 大模型交叉精排”的双重检索机制，确保合规建议 100% 准确。
- 🛠️ **全面拥抱 `agentskills.io` 开放标准**：
  - 系统内置 `data-visualization` 与 `docx-assembler` 等原子技能包。
  - 大模型通过阅读 `SKILL.md`（技能说明书），自主编写 Python 绘图和 Word 排版代码。
  - 在本地 Code Interpreter 沙盒中执行代码，凭空生成完美组装的数据图表与 `.docx` 报告。
- ⚡ **早退机制 (Early-Exit Reflection)**：内置 `TrafficReportReflector` 反思状态机，专家模型对生成的报告进行自查，若满足要求则触发 `PASS` 信号提前结束迭代，大幅降低延迟。

---

## 🛠️ 技术栈 (Tech Stack)

- **框架**: LangChain, LangGraph (状态机设计理念)
- **大模型**: OpenAI 兼容接口 (如 GPT-4, Claude-3 等)
- **知识库**: ChromaDB + RecursiveCharacterTextSplitter
- **前端交互**: Streamlit
- **多模态扩展**: Matplotlib (动态折线图), python-docx (企业红头文件装配)

---

## 📂 技能架构 (Agent Skills Architecture)

本项目严格遵循前沿的智能体解耦设计，所有排版和图表能力均抽象为独立的 Skill 文件夹：

```text
agent/skills/
├── data-visualization/
│   └── SKILL.md          # 告诉模型如何用 matplotlib 将查到的数据画成折线图
├── compliance-sop/
│   ├── SKILL.md          # 指导模型遇到事故时如何去查下方的预案库
│   └── resources/
│       └── database.json # 官方标准处置预案
└── docx-assembler/
    └── SKILL.md          # 指导模型如何用 python-docx 拼接图文，生成最终报告
```

---

## 🚀 快速启动 (Quick Start)

### 1. 克隆代码
```bash
git clone https://github.com/cxs-wuanjun/Agentic-Traffic-Diagnoser.git
cd Agentic-Traffic-Diagnoser
```

### 2. 配置环境
```bash
conda create -n agent python=3.10
conda activate agent
pip install -r requirements.txt
```

### 3. 环境变量
在项目根目录创建 `.env` 文件并填入以下信息：
```ini
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=https://api.xxxx.com/v1
GAODE_API_KEY=你的高德地图Web服务Key
```

### 4. 运行服务
```bash
streamlit run app.py
```
> 服务启动后，浏览器将自动打开 `http://localhost:8501`。你可以输入：“帮我生成中山路的综合交通诊断报告”。

---

## 🤝 贡献与许可 (License)
MIT License. 欢迎提交 PR 一起完善这个交通智能体生态！
