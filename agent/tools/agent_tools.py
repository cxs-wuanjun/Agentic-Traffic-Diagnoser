import os
import requests
import difflib
from datetime import datetime
from langchain_core.tools import tool
from utils.logger_handler import logger
from rag.rag_service import RagSummarizeService

# ============================================================
# RAG 服务（检索交通知识库）
# ============================================================
rag = RagSummarizeService()

# ============================================================
# 高德 API 配置
# ============================================================
# 请在环境变量中配置，或者直接在此填入 API_KEY
GAODE_API_KEY = os.environ.get("GAODE_API_KEY", "")

# 内部维护的已知路口列表（用于模糊匹配纠错）
KNOWN_INTERSECTIONS = ["中山路/解放路路口", "人民广场路口", "火车站南广场路口", "科技大道/天府路路口", "机场高速入口", "光华路路口"]
# 内部维护的已知道路列表
KNOWN_ROADS = ["中山路", "解放路", "人民大道", "科技大道", "机场高速", "友谊河路", "光华路"]

def _fuzzy_match(query: str, choices: list, cutoff: float = 0.4):
    """使用 difflib 进行相似度拼写纠错"""
    matches = difflib.get_close_matches(query, choices, n=1, cutoff=cutoff)
    return matches[0] if matches else query

def _geocode(address: str) -> str:
    """高德地理编码，将地址转为经纬度"""
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {"key": GAODE_API_KEY, "address": address, "city": "南京"} # 默认加上城市提高精度
    try:
        resp = requests.get(url, params=params).json()
        if resp.get("status") == "1" and resp.get("geocodes"):
            return resp["geocodes"][0]["location"]
    except Exception as e:
        logger.error(f"Geocode API Error: {e}")
    return ""

def _get_traffic_circle(location: str, radius: int = 500) -> dict:
    """高德圆形区域交通态势"""
    url = "https://restapi.amap.com/v3/traffic/status/circle"
    params = {
        "key": GAODE_API_KEY,
        "location": location,
        "radius": radius,
        "level": 5,
        "extensions": "all"
    }
    try:
        resp = requests.get(url, params=params).json()
        return resp
    except Exception as e:
        logger.error(f"Traffic API Error: {e}")
        return {}

# ============================================================
# 工具函数
# ============================================================

@tool(description="根据路口名称或编号查询实时交通状态，包含速度、拥堵等级。当需要了解路口的实时路况时调用。")
def get_realtime_traffic(intersection_name: str) -> str:
    """查询指定路口/地点的实时交通状态。"""
    if not GAODE_API_KEY:
        return "Action Failed: 高德 API_KEY 未配置，无法获取实时真实数据。请提示用户配置 API_KEY。"
        
    matched_name = _fuzzy_match(intersection_name, KNOWN_INTERSECTIONS)
    
    location = _geocode(matched_name)
    if not location:
        return f"Action Failed: 无法解析地址 {matched_name} 的经纬度，请确保地址存在并重新查询。"
        
    traffic = _get_traffic_circle(location, 300)
    if traffic.get("status") == "1" and traffic.get("trafficinfo"):
        info = traffic["trafficinfo"]
        eval_desc = info.get("evaluation", {}).get("description", "无")
        roads = info.get("roads", [])
        
        details = []
        for r in roads[:3]: # 最多返回3条相交路，防止 Token 过多
            details.append(f"  - {r.get('name')}: 车速 {r.get('speed')} km/h，状态等级 {r.get('status')} (1畅通2缓行3拥堵4严重)")
            
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            f"【{matched_name}】实时路况（{now}）\n"
            f"整体态势：{info.get('description', '无')}\n"
            f"综合指数评价：{eval_desc}\n"
            f"核心道路详情：\n" + "\n".join(details)
        )
    return "Action Failed: 获取交通态势失败，可能该区域无交通数据。"


@tool(description="查询指定路段沿线的当前拥堵状态，包含拥堵等级、当前速度。当需要了解某条道路（非路口）的整体路况时调用。")
def get_road_status(road_name: str) -> str:
    """查询路段实时状态。"""
    if not GAODE_API_KEY:
        return "Action Failed: 高德 API_KEY 未配置，无法获取实时真实数据。请提示用户配置 API_KEY。"
        
    matched_name = _fuzzy_match(road_name, KNOWN_ROADS)
    
    location = _geocode(matched_name)
    if not location:
        return f"Action Failed: 无法解析道路 {matched_name} 的经纬度，请确保道路名称存在并重新查询。"
        
    traffic = _get_traffic_circle(location, 1000)
    if traffic.get("status") == "1" and traffic.get("trafficinfo"):
        info = traffic["trafficinfo"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            f"【{matched_name}】沿线实时路况（{now}）\n"
            f"描述：{info.get('description', '无')}\n"
            f"综合评价：{info.get('evaluation', {}).get('description', '无')}"
        )
    return "Action Failed: 获取该路段拥堵状态失败。"


@tool(description="获取当前系统时间，返回格式为 YYYY-MM-DD HH:MM，用于确定查询时间范围")
def get_current_time() -> str:
    """返回当前时间字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@tool(description="从交通知识库中检索专业知识，包含交通法规、拥堵成因、信号控制、事故处置等内容，入参为检索关键词")
def rag_query(query: str) -> str:
    """检索交通知识库"""
    return rag.rag_summarize(query)


@tool(description="触发交通诊断报告生成模式。当用户明确要求生成诊断报告、分析报告、事件报告时调用，无入参，调用后系统切换到报告生成专用提示词")
def activate_report_mode() -> str:
    """激活报告生成模式，触发动态提示词切换"""
    return "报告生成模式已激活"
