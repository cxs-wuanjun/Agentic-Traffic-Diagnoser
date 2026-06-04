---
name: docx-assembler
description: 当需要将最终的 Markdown 报告、图表图片和附加文本组装成企业级 Word 文档 (.docx) 格式时使用。
dependencies: python-docx
---

# Word 红头文件排版 (Docx Assembler) 技能手册

当任务要求最终输出一份完整的交通诊断报告时，除了输出文字，你还需要在回答的末尾提供一段完整的 Python 代码（使用 ```python 包裹）。
这段代码负责读取你刚才生成的图表（如果有的话）以及你的正文，并排版生成一个企业级的 `.docx` 文件。

## 排版规范
1. 依赖库为 `python-docx`。
2. 必须在第一页顶部生成居中、加粗、红色的字号 22 的标题（比如“交通诊断评估报告”）。
3. 如果 `outputs/reports/chart.png` 存在，必须将它插入到文档的适当位置（通常在第一段分析之后）。
4. 文件**必须**保存为 `outputs/reports/Final_Report.docx`。

## 代码范例

```python
import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()
# 标题
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run("交通智能诊断评估报告")
run.font.size = Pt(22)
run.font.bold = True
run.font.color.rgb = RGBColor(0xCC, 0x00, 0x00)
doc.add_paragraph("").add_run("_" * 60)

# 正文 (你可以将你的诊断结论浓缩写入)
doc.add_heading("1. 诊断分析", level=1)
doc.add_paragraph("经查，目标区域历史拥堵数据存在波动...")

# 插入图片
chart_path = os.path.join(os.getcwd(), "outputs", "reports", "chart.png")
if os.path.exists(chart_path):
    doc.add_heading("2. 数据可视化", level=1)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(chart_path, width=Inches(6.0))

# 预案
doc.add_heading("3. 处置建议", level=1)
doc.add_paragraph("建议加强警力疏导...")

out_dir = os.path.join(os.getcwd(), "outputs", "reports")
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, "Final_Report.docx")
doc.save(out_file)
print(f"Word文件已生成: {out_file}")
```
