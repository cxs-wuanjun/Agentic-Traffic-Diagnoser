import os
import matplotlib.pyplot as plt

def draw_trend_chart(dates: list[str], values: list[float], title: str = "交通趋势分析") -> str:
    """
    统一的交通数据折线图绘制引擎
    返回生成的图片绝对路径
    """
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    plt.figure(figsize=(8, 4))
    plt.plot(dates, values, marker='o', color='#d32f2f', linewidth=2.5)
    plt.fill_between(dates, values, color='#ef5350', alpha=0.2)
    plt.title(title)
    plt.xlabel("日期")
    plt.ylabel("数值")
    plt.grid(True, linestyle='--', alpha=0.5)

    out_dir = os.path.join(os.getcwd(), "outputs", "reports")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "chart.png")
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    
    return out_path
