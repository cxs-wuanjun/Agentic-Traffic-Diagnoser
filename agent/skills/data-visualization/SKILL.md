---
name: data-visualization
description: 当你拥有一组历史交通数据并需要生成直观的折线图以插入报告时，使用此技能编写 matplotlib 代码。
dependencies: matplotlib, datetime
---

# 数据可视化 (Data Visualization) 技能手册

当任务需要你绘制“拥堵延时指数”或“交通流量”趋势图时，请严格根据你在上下文中**已经查到的真实数据**，在你的最终回答中输出一段 Python 代码（包裹在 ```python 和 ``` 之间）。

## 绘图要求
1. 使用 `matplotlib.pyplot`。
2. 必须设置中文字体：`plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']`。
3. 请使用 `plt.plot()` 绘制带有 marker 的折线图，并用 `plt.fill_between()` 在下方填充颜色。
4. 图片**必须**保存到当前目录的 `outputs/reports/chart.png`。
5. 必须在代码末尾显式 `plt.close()`。

## 代码范例

```python
import os
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

# 请将这里的 dates 和 values 替换为你查到的真实数据
dates = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
values = [1.5, 1.8, 2.1, 1.9, 2.5, 1.2, 1.3]

plt.figure(figsize=(8, 4))
plt.plot(dates, values, marker='o', color='#d32f2f', linewidth=2.5)
plt.fill_between(dates, values, color='#ef5350', alpha=0.2)
plt.title("交通趋势分析")
plt.xlabel("日期")
plt.ylabel("数值")
plt.grid(True, linestyle='--', alpha=0.5)

out_dir = os.path.join(os.getcwd(), "outputs", "reports")
os.makedirs(out_dir, exist_ok=True)
plt.tight_layout()
plt.savefig(os.path.join(out_dir, "chart.png"), dpi=150)
plt.close()
print(f"图表已生成: {os.path.join(out_dir, 'chart.png')}")
```
