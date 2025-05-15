import os
from multi_bus_tracker import MultiBusTracker, BusDataCollector
from check_validate_key import validate_api_key

# 데이터 저장 디렉토리 생성
os.makedirs("bus/data", exist_ok=True)
os.makedirs("bus/data/multi_route", exist_ok=True)

def main():
    # 공공데이터포털 API 키 입력
    API_KEY = ""

    file_path="api_key.txt"

    if API_KEY == "":
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                API_KEY = f.read().strip()

            if API_KEY:
                print(f"API 키가 '{file_path}'에서 성공적으로 로드되었습니다.")
                return API_KEY
            else:
                print(f"'{file_path}' 파일이 비어 있습니다.")
        else:
            print(f"'{file_path}' 파일이 존재하지 않습니다.")

    # if not validate_api_key(API_KEY):
    #     exit(1)  # 인증 실패 시 종료
    
    # 다중 경로 추적기 초기화
    tracker = MultiBusTracker(api_key=API_KEY)
    
    print("다중 경로 버스 추적 시스템이 시작되었습니다.")
    print("설정된 경로 정보:")
    
    # 경로 1: 262번 버스 국민은행장안동지점 → 청량리.청과물도매시장
    #tracker.add_route(
    #    route_id="262_jangan_cheongnyangni",
    #    bus_route_name="262",
    #    start_station="국민은행장안동지점",
    #    end_station="청량리.청과물도매시장",
    #    time_predictions={
    #        '8:00-9:40': 17,
    #        '9:50': 16,
    #        '10:00': 16
    #    }
    #)
    #print("- 경로 1: 262번 버스 (국민은행장안동지점 → 청량리.청과물도매시장)")
    
    # 경로 2: 2115번 버스 청량리.청과물도매시장 → 안암오거리
    tracker.add_route(
        route_id="2115_cheongnyangni_anam",
        bus_route_name="2115",
        start_station="청량리.청과물도매시장",
        end_station="안암오거리",
        time_predictions={
            '8:00-10:00': 7,
            '17:00-19:00': 7
        }
    )
    print("- 경로 2: 2115번 버스 (청량리.청과물도매시장 → 안암오거리)")
    
    # 경로 3: 271번 버스 광화문역 → 홍대입구역
    tracker.add_route(
        route_id="271_gwanghwamun_hongdae",
        bus_route_name="271",
        start_station="광화문역",
        end_station="홍대입구역",
        time_predictions={
            '8:00-10:00': 21,
            '17:00-19:00': 23
        }
    )
    print("- 경로 3: 271번 버스 (광화문역 → 홍대입구역)")
    
    # 경로 4: 440번 버스 지하철2호선강남역 → 신사역3번출구
    tracker.add_route(
        route_id="440_gangnam_sinsa",
        bus_route_name="440",
        start_station="지하철2호선강남역",
        end_station="신사역3번출구",
        time_predictions={
            '8:00-8:10': 4,
            '8:20-8:40': 6,
            '8:50-10:00': 4,
            '17:00-19:00': 4
        }
    )
    print("- 경로 4: 440번 버스 (지하철2호선강남역 → 신사역3번출구)")
    
    # 경로 5: 144번 버스 동대문역사문화공원역8번출구 → 신사역.푸른저축은행
    tracker.add_route(
        route_id="144_dongdaemun_sinsa",
        bus_route_name="144",
        start_station="동대문역사문화공원역8번출구",
        end_station="신사역.푸른저축은행",
        time_predictions={
            '8:00-8:40': 23,
            '8:50-9:40': 24,
            '9:50': 23,
            '10:00': 22,
            '17:00-17:40': 24,
            '17:50-18:40': 23,
            '18:50': 22,
            '19:00': 21
        }
    )
    print("- 경로 5: 144번 버스 (동대문역사문화공원역8번출구 → 신사역.푸른저축은행)")
    
    print("\n모든 경로 설정이 완료되었습니다.")
    
    # 추적 시간 설정
    duration_minutes = int(input("\n추적 지속 시간(분)을 입력하세요 (기본값: 60): ") or "60")
    interval_seconds = int(input("위치 확인 간격(초)을 입력하세요 (기본값: 15): ") or "15")
    parallel_mode = input("병렬 추적 모드를 사용하시겠습니까? (y/n, 기본값: y): ").lower() != 'n'
    
    print(f"\n{'병렬' if parallel_mode else '순차'} 추적 모드로 {duration_minutes}분 동안 {interval_seconds}초 간격으로 추적을 시작합니다...")
    print("(추적을 중단하려면 Ctrl+C를 누르세요)\n")
    
    # 모든 경로 추적 실행
    tracker.track_all_routes(
        duration_minutes=duration_minutes, 
        interval_seconds=interval_seconds, 
        parallel=parallel_mode
    )
    
    # 종합 분석 보고서 생성
    print("\n추적이 완료되었습니다. 종합 분석 보고서를 생성합니다...")
    combined_results = tracker.generate_combined_analysis()
    
    print("\n데이터 수집 및 분석이 완료되었습니다.")
    print(f"결과 파일은 bus/data/multi_route/ 폴더에 저장되었습니다.")
    
    # 결과 요약 출력
    print("\n=== 경로별 예측 소요 시간과의 비교 결과 ===")
    for route_id, summary in tracker.summary_data.items():
        route_info = tracker.collectors[route_id]
        print(f"\n{route_info['bus_route_name']}번 버스 ({route_info['start_station']} → {route_info['end_station']})")
        print(f"- 평균 오차: {summary.get('avg_difference', 'N/A')}분")
        print(f"- 표준편차: {summary.get('std_difference', 'N/A')}분")
        print(f"- 최대 오차: {summary.get('max_difference', 'N/A')}분")
        print(f"- 최소 오차: {summary.get('min_difference', 'N/A')}분")
        print(f"- 추적 기록 수: {summary.get('records_count', 0)}개")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"\n오류가 발생했습니다: {str(e)}")
    finally:
        print("\n프로그램을 종료합니다.")