import requests
import xml.etree.ElementTree as ET

def validate_api_key(api_key):
    """
    서울 열린데이터광장 API 키가 아래 3개 API에서 유효한지 확인:
    1. 노선 검색 API (getBusRouteList) - JSON
    2. 정류장 리스트 API (getStaionByRoute) - JSON
    3. 실시간 버스 위치 API (getBusPosByRtid) - XML
    """
    base_url = "http://ws.bus.go.kr/api/rest"

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
        "busRouteId": "100100549",  # 예: 100번
        "resultType": "json"
    }

    # 3. 실시간 버스 위치 API
    bus_pos_url = f"{base_url}/buspos/getBusPosByRtid"
    bus_pos_params = {
        "serviceKey": api_key,
        "busRouteId": "100100549"  # 동일 노선 ID
    }

    def check_api(name, url, params, is_xml=False):
        try:
            response = requests.get(url, params=params, timeout=5)

            if is_xml:
                root = ET.fromstring(response.content)
                header_cd = root.findtext(".//headerCd")
                header_msg = root.findtext(".//headerMsg")
            else:
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
            print(f"❌ {name} 호출 오류: {e}")
            print("응답 내용:", response.text[:300])
            return False

    print("🔐 API 키 인증 확인 중...\n")

    ok1 = check_api("노선 검색 API", route_list_url, route_params, is_xml=False)
    ok2 = check_api("정류장 리스트 API", station_list_url, station_params, is_xml=False)
    ok3 = check_api("실시간 버스 위치 API", bus_pos_url, bus_pos_params, is_xml=True)

    if ok1 and ok2 and ok3:
        print("\n✅ 모든 API 인증 성공 — 실행을 계속합니다.\n")
        return True
    else:
        print("\n🚫 하나 이상의 API 인증 실패 — 프로그램을 종료합니다.\n")
        return False