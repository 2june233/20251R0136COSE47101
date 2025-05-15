import requests

def validate_api_key(api_key):
    """
    서울 열린데이터광장 API 키가 아래 3개 API에서 유효한지 확인:
    1. 노선 검색 API (getBusRouteList)
    2. 정류장 리스트 API (getStaionByRoute)
    3. 실시간 버스 위치 API (getBusPosByRtid)
    """
    base_url = "http://ws.bus.go.kr/api/rest"

    # 테스트에 사용할 안정적인 노선 (271번)
    route_id = "100100118"  # 271번

    # 1. 노선 검색 API
    route_list_url = f"{base_url}/busRouteInfo/getBusRouteList"
    route_params = {
        "serviceKey": api_key,
        "strSrch": "271",
        "resultType": "json"
    }

    # 2. 정류장 리스트 API
    station_list_url = f"{base_url}/busRouteInfo/getStaionByRoute"
    station_params = {
        "serviceKey": api_key,
        "busRouteId": route_id,
        "resultType": "json"
    }

    # 3. 실시간 버스 위치 API
    bus_pos_url = f"{base_url}/buspos/getBusPosByRtid"
    bus_pos_params = {
        "serviceKey": api_key,
        "busRouteId": route_id,
        "resultType": "json"
    }

    def check_api(name, url, params):
        try:
            print(f"\n🔍 {name} 요청 중...")
            response = requests.get(url, params=params, timeout=5)
            print(f"HTTP 상태 코드: {response.status_code}")
            print("응답 내용 일부:", response.text[:200])

            data = response.json()
            header = data.get('msgHeader', {})
            header_cd = header.get("headerCd")
            header_msg = header.get("headerMsg")

            if header_cd == "0":
                print(f"✅ {name} 인증 성공")
                return True
            else:
                print(f"❌ {name} 인증 실패: {header_msg} (코드: {header_cd})")
                return False

        except Exception as e:
            print(f"❌ 예외 발생: {e}")
            print("응답 내용:", response.text[:300])
            return False

    print("🔐 API 키 인증 확인 중...\n")

    ok1 = check_api("노선 검색 API", route_list_url, route_params)
    ok2 = check_api("정류장 리스트 API", station_list_url, station_params)
    ok3 = check_api("실시간 버스 위치 API", bus_pos_url, bus_pos_params)

    if ok1 and ok2 and ok3:
        print("\n✅ 모든 API 인증 성공 — 실행을 계속합니다.\n")
        return True
    else:
        print("\n🚫 하나 이상의 API 인증 실패 — 프로그램을 종료합니다.\n")
        return False
