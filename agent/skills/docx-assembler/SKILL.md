---
name: docx-assembler
description: 当需要将最终的 Markdown 报告、图表图片和附加文本组装成企业级 Word 文档 (.docx) 格式时使用。
dependencies: python-docx
---

# Word 红头文件排版 (Docx Assembler) 技能手册

当任务要求最终输出一份完整的交通诊断报告时，除了输出文字，你还需要在回答的末尾提供一段完整的 Python 代码（使用 ```python 包裹）。
这段代码负责调用我们的排版引擎，将图表（如果有的话）以及你的正文，组装成企业级的 `.docx` 文件。

## 排版规范
1. 必须调用预置的 Word 排版引擎。
2. 引擎会自动处理红头文件格式和图片插入。

## 代码范例

```python
import importlib
build_word = importlib.import_module("agent.skills.docx-assembler.scripts.build_word")

# 请传入你总结好的 Markdown 文本、刚刚生成的图表路径、以及提取出的 SOP（如果有）
content = "经查，目标区域历史拥堵数据存在波动..."
chart_path = "outputs/reports/chart.png" # 必须是上面可视化的真实输出路径
sop_content = "建议加强警力疏导..."

out_file = build_word.create_report(content=content, chart_path=chart_path, sop_content=sop_content)
print(f"Word文件已生成: {out_file}")
```
