import os
import sqlite3
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage

# 从配置或公共库中导入模型
# 注意：这需要确保你的项目中可以调用获取模型的工厂函数，我们这里简单引用一个
try:
    from model.llm_factory import get_model  # 假设你有这个工厂
except:
    # 兼容性备用方案
    from langchain_openai import ChatOpenAI
    def get_model():
        return ChatOpenAI(model="qwen-max", temperature=0, base_url=os.environ.get("OPENAI_BASE_URL"), api_key=os.environ.get("OPENAI_API_KEY"))

# 替换为你实际的数据库路径
DB_PATH = r"D:\python_project\Agent_\test2sql\test2sql\backend\db\my_database.db"

# 数据库中交通相关表的简化 Schema 提示
SCHEMA_PROMPT = """你是一个专业的 SQLite 数据库分析师。
数据库中有一张历史交通表 traffic_road_section_health，包含以下可用字段：
- road_name (TEXT): 道路名称，如 '中山路'
- category_cn (TEXT): 道路类型
- stat_period (TEXT): 统计日期，如 '2023-10-01'
- time_period (TEXT): 时间段，如 '08:00'
- `拥堵延时指数` (FLOAT): 拥堵程度
- `高峰平均速度` (FLOAT): 高峰时段的平均速度 (km/h)

请根据用户的查询意图，写出一条标准的 SQLite SQL 查询语句。
要求：
1. 你的回答必须只能包含 SQL 语句本身，不能包含 ```sql 标记、注释或任何额外的解释性文本。
2. 尽量使用 LIKE 进行模糊匹配，并且使用 LIMIT 10 限制返回行数。
"""

@tool(description="查询历史交通数据库。当需要对比历史车速、历史拥堵数据来判断当前路况是否异常时使用。入参是具体的自然语言查询意图。")
def analyze_historical_traffic_sql(query: str) -> str:
    """
    分析历史交通数据 (Text-to-SQL 工具)。
    传入自然语言查询意图，如："查询中山路历史平均车速"
    """
    if not os.path.exists(DB_PATH):
        return "Action Failed: 本地历史数据库文件不存在，请检查路径配置。"

    try:
        model = get_model()
        messages = [
            SystemMessage(content=SCHEMA_PROMPT),
            HumanMessage(content=f"用户意图: {query}\n请输出 SQLite 语句:")
        ]
        
        # 1. 大模型将自然语言转为 SQL
        sql_response = model.invoke(messages)
        sql_query = sql_response.content.strip()
        
        # 清理可能包含的 Markdown 标记
        if sql_query.startswith("```"):
            sql_query = "\n".join(sql_query.split("\n")[1:-1])
            
        sql_query = sql_query.replace("```", "").strip()

        # 2. 在本地 SQLite 数据库中执行 SQL
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 安全限制：防止恶意删除
        if "DROP" in sql_query.upper() or "DELETE" in sql_query.upper() or "UPDATE" in sql_query.upper():
            return "Action Failed: 出于安全考虑，仅允许执行 SELECT 查询。"

        cursor.execute(sql_query)
        columns = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        conn.close()
        
        # 3. 组装结果返回给大模型
        if not results:
            return f"执行 SQL: {sql_query}\n结果: 未查询到符合条件的历史数据。"
            
        # 格式化输出，防止内容过长
        result_str = f"执行 SQL: {sql_query}\n查询结果(列名: {columns}):\n"
        for i, row in enumerate(results[:5]): # 最多只给前 5 条，防止 Token 爆炸
            result_str += f"  {i+1}. {row}\n"
            
        return result_str

    except Exception as e:
        return f"Action Failed: SQL 工具执行失败。错误原因: {str(e)}。SQL语句可能是: {sql_query}"
