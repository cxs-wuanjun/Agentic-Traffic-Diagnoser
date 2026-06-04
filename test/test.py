import requests
import json

# ==========================================
# 高德地图 Web服务 API 测试脚本
# ==========================================
# 请将你在高德开放平台申请的 Web服务 Key 填入下方
API_KEY = "d3619ec3c3759a20ffb3a8beac956e1b"

# 测试用例：我们要查“杭州市中山北路”的路况
TEST_ADDRESS = "南京市光华路"


def test_gaode_api():
    if API_KEY == "在这里填入你的_API_KEY":
        print("❌ 请先将代码中的 API_KEY 替换为你申请的真实 Key！")
        return

    print("==================================================")
    print(f"开始测试高德 API，查询目标：{TEST_ADDRESS}")
    print("==================================================\n")

    # ---------------------------------------------------------
    # 第一步：调用【地理编码 API】将文字地址转换为经纬度坐标
    # ---------------------------------------------------------
    print("⏳ [1/2] 正在调用【地理编码 API】...")
    geo_url = "https://restapi.amap.com/v3/geocode/geo"
    geo_params = {
        "key": API_KEY,
        "address": TEST_ADDRESS,
        "city": "南京"  # 可选，限定城市能提高准确率
    }

    try:
        geo_response = requests.get(geo_url, params=geo_params)
        geo_data = geo_response.json()

        # 只打印核心结果，方便查看
        print("✅ 地理编码 API 返回原始数据：")
        print(json.dumps(geo_data, indent=4, ensure_ascii=False))

        if geo_data.get("status") != "1" or not geo_data.get("geocodes"):
            print("\n❌ 地理编码失败，请检查 Key 或地址是否正确。")
            return

        # 提取第一个匹配结果的经纬度
        location = geo_data["geocodes"][0]["location"]
        print(f"\n📍 提取到【{TEST_ADDRESS}】的中心坐标为：{location}\n")

    except Exception as e:
        print(f"地理编码请求发生异常: {e}")
        return

    # ---------------------------------------------------------
    # 第二步：调用【圆形区域交通态势 API】获取路况
    # ---------------------------------------------------------
    # 由于路口是一个点，我们以该点为中心，查询半径 200 米内的交通态势
    print("⏳ [2/2] 正在调用【圆形区域交通态势 API】...")
    traffic_url = "https://restapi.amap.com/v3/traffic/status/circle"
    traffic_params = {
        "key": API_KEY,
        "location": location,  # 格式: 经度,纬度
        "radius": 200,  # 半径，单位：米，最大支持 5000
        "level": 5,  # 道路等级：5代表所有道路
        "extensions": "all"  # 返回详细路段信息
    }

    try:
        traffic_response = requests.get(traffic_url, params=traffic_params)
        traffic_data = traffic_response.json()

        print("✅ 圆形区域交通态势 API 返回原始数据：")
        # 为防止返回数据过长刷屏，只打印 json，你可以自己查看结构
        print(json.dumps(traffic_data, indent=4, ensure_ascii=False))

        if traffic_data.get("status") == "1" and traffic_data.get("trafficinfo"):
            info = traffic_data["trafficinfo"]
            print("\n🚗 --- 核心交通数据解析 ---")
            print(f"整体评价：{info.get('description', '无描述')}")
            print(f"整体拥堵指数：{info.get('evaluation', {}).get('expedite', 'N/A')}")
            print(f"包含的道路数量：{len(info.get('roads', []))} 条")

            # 打印其中一条道路的样例
            if info.get("roads"):
                sample_road = info["roads"][0]
                print(f"\n🛣️ 样例路段：{sample_road.get('name', '未知路名')}")
                print(f"  - 拥堵状态：{sample_road.get('status')} (0:未知, 1:畅通, 2:缓行, 3:拥堵, 4:严重拥堵)")
                print(f"  - 平均车速：{sample_road.get('speed', '未知')} km/h")
        else:
            print("\n❌ 获取路况失败，可能是区域内无数据或接口权限限制。")
            print(f"状态码: {traffic_data.get('infocode')}, 信息: {traffic_data.get('info')}")

    except Exception as e:
        print(f"交通态势请求发生异常: {e}")


if __name__ == "__main__":
    test_gaode_api()