---
name: compliance-sop
description: 根据交通异常类型读取内置 SOP 预案库，约束报告中的处置建议和 Word 附录。
dependencies: json
---

# 合规预案 (Compliance SOP) 技能手册

在撰写最终报告的“处置建议”环节，你不能自行编造建议，必须严格引用官方预案库中的原文。

## 操作指南
请调用我们封装好的预案检索模块，传入当前异常类型（例如“拥堵”、“事故”、“施工”），提取原文：

```python
import importlib
search_sop = importlib.import_module("agent.skills.compliance-sop.scripts.search_sop")

# 根据诊断结果拉取预案
sop_text = search_sop.fetch_sop("事故")
print("找到预案:", sop_text)
```

## 使用规则

1. 在 Draft 阶段就需要根据当前报告中的异常类型生成处置建议，不能只在最终 Word 装配时补充。
2. 如果能判断异常类型，优先读取对应 SOP；如果无法判断，必须说明“当前数据不足以判断异常类型”，并给出保守的后续监测建议。
3. 处置建议应写入报告正文的“处置建议”章节；如果生成 Word，可同时作为附录写入。
4. 不能把内置 SOP 预案库包装成真实外部官方文件，除非工具或知识库返回了明确来源。
5. 建议必须具体、可执行，避免“加强管理、持续关注”这类空泛表达。

## 推荐生成方式

- 拥堵：可围绕疏导、诱导、分流、重点方向通行能力、后续监测展开。
- 事故：可围绕快速到场、现场保护、清障、医疗联动、二次事故预防展开。
- 施工：可围绕警示标志、物理隔离、临时限速、绕行提示展开。

## Python 读取示例

```python
import json
import os

db_path = os.path.join(
    os.getcwd(),
    "agent",
    "skills",
    "compliance-sop",
    "resources",
    "database.json",
)

with open(db_path, "r", encoding="utf-8") as f:
    sop_db = json.load(f)

abnormal_type = "拥堵"
sop_text = sop_db.get(abnormal_type, sop_db.get("拥堵", ""))
```
