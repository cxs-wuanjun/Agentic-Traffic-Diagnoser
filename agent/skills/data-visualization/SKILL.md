---
name: data-visualization
description: 当你拥有一组历史交通数据并需要生成直观的折线图以插入报告时，使用此技能编写 matplotlib 代码。
dependencies: matplotlib, datetime
---

# 数据可视化 (Data Visualization) 技能手册

当任务需要你绘制“拥堵延时指数”或“交通流量”趋势图时，请严格根据你在上下文中**已经查到的真实数据**，在你的最终回答中输出一段 Python 代码（包裹在 ```python 和 ``` 之间），调用我们封装好的图表引擎。

## 绘图要求
1. 你必须调用预置的画图引擎：`agent.skills.data-visualization.scripts.plot_chart.draw_trend_chart`
2. 将你查找到的数据以 list 形式传入 `dates` 和 `values` 参数。
3. 引擎会自动保存图片并返回路径。

## 代码范例

```python
from agent.skills.getattr('data-visualization', 'scripts.plot_chart').draw_trend_chart import draw_trend_chart
# 或者直接：
import sys
sys.path.append('.')
from agent.skills.getattr("data-visualization").scripts.plot_chart import draw_trend_chart # 为了避免 - 报错，最好用下面安全导入方式

import importlib
plot_chart = importlib.import_module("agent.skills.data-visualization.scripts.plot_chart")

# 请替换为你查到的真实数据
dates = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
values = [1.5, 1.8, 2.1, 1.9, 2.5, 1.2, 1.3]

chart_path = plot_chart.draw_trend_chart(dates=dates, values=values, title="历史交通趋势分析")
print(f"图表已生成: {chart_path}")
```
