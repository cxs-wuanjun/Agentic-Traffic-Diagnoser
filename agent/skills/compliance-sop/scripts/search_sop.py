import os
import json

def fetch_sop(keyword: str) -> str:
    """
    根据关键字匹配最新的国家标准处置预案
    """
    db_path = os.path.join(os.getcwd(), "agent", "skills", "compliance-sop", "resources", "database.json")
    
    if not os.path.exists(db_path):
        return ""
        
    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for k, v in data.items():
        if k in keyword:
            return v
            
    # 默认 fallback
    return data.get("拥堵", "")
