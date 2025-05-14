import requests
import time
import pandas as pd
from datetime import datetime
import os
import logging
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bus/data/bus_tracker.log"),
        logging.StreamHandler()
    ]
)

class BusDataCollector:
    def __init__(self, api_key, bus_route_name=None, bus_route_id=None, start_station=None, end_station=None):
        """
        서울시 버스 데이터 수집기 초기화

        Parameters:
        -----------
        api_key : str
            서울 열린데이터광장 API 키
        bus_route_name : str
            버스 노선명 (예: "6411")
        bus_route_id : str
            버스 노선 ID (이미 알고 있는 경우)
        start_station : str
            출발 정류장명
        end_station : str
            도착 정류장명
        """
        self.api_key = api_key
        self.bus_route_name = bus_route_name
        self.bus_route_id = bus_route_id
        self.start_station = start_station
        self.end_station = end_station

        # 결과 저장용 변수
        self.route_info = None
        self.station_list = []
        self.start_station_id = None
        self.end_station_id = None
        self.start_station_ord = None
        self.end_station_ord = None
        self.bus_tracking_data = {}  # 실시간 버스 추적 데이터
        self.travel_records = []     # 계산된 여행 시간 기록

        # 데이터 파일명
        self.data_filename = f"bus/data/bus_{bus_route_name}_data.csv"

        # 초기 설정
        if self.bus_route_id is None and self.bus_route_name is not None:
            self.get_route_id()

        if self.bus_route_id is not None:
            self.get_station_list()

            if self.start_station is not None and self.end_station is not None:
                self.set_tracking_stations()

    def get_route_id(self):
        """버스 노선명으로 노선 ID 조회"""
        url = "http://ws.bus.go.kr/api/rest/busRouteInfo/getBusRouteList"
        params = {
            "serviceKey": self.api_key,
            "strSrch": self.bus_route_name,
            "resultType": "json"
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if response.status_code == 200 and data.get('msgHeader', {}).get('headerCd') == '0':
                items = data.get('msgBody', {}).get('itemList', [])

                for item in items:
                    if item.get('busRouteNm') == self.bus_route_name:
                        self.bus_route_id = item.get('busRouteId')
                        self.route_info = item
                        logging.info(f"노선 ID 확인: {self.bus_route_name} -> {self.bus_route_id}")
                        return True

                logging.warning(f"노선을 찾을 수 없음: {self.bus_route_name}")
                return False
            else:
                logging.error(f"API 호출 실패: {data.get('msgHeader', {}).get('headerMsg')}")
                return False

        except Exception as e:
            logging.error(f"노선 ID 조회 중 오류: {str(e)}")
            return False

    def get_station_list(self):
        """버스 노선의 정류장 목록 조회"""
        url = "http://ws.bus.go.kr/api/rest/busRouteInfo/getStaionByRoute"
        params = {
            "serviceKey": self.api_key,
            "busRouteId": self.bus_route_id,
            "resultType": "json"
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if response.status_code == 200 and data.get('msgHeader', {}).get('headerCd') == '0':
                items = data.get('msgBody', {}).get('itemList', [])
                self.station_list = items

                # 정류장 정보 출력
                #for i, station in enumerate(items[:5]):  # 처음 5개만 출력
                #    logging.info(f"정류장 {i+1}: {station.get('stationNm')} (ID: {station.get('station')}, 순번: {station.get('seq')})")
#
                #if len(items) > 5:
                #    logging.info(f"... 외 {len(items) - 5}개 정류장")

                return True
            else:
                logging.error(f"정류장 목록 조회 실패: {data.get('msgHeader', {}).get('headerMsg')}")
                return False

        except Exception as e:
            logging.error(f"정류장 목록 조회 중 오류: {str(e)}")
            return False

    def set_tracking_stations(self):
        """추적할 출발/도착 정류장 설정"""
        start_matches = [s for s in self.station_list if self.start_station in s.get('stationNm', '')]
        end_matches = [s for s in self.station_list if self.end_station in s.get('stationNm', '')]

        if start_matches and end_matches:
            # 가장 첫 번째 일치하는 항목 선택
            start_station = start_matches[0]
            end_station = end_matches[0]

            self.start_station_id = start_station.get('station')
            self.end_station_id = end_station.get('station')
            self.start_station_ord = int(start_station.get('seq'))
            self.end_station_ord = int(end_station.get('seq'))

            logging.info(f"추적 설정: {start_station.get('stationNm')}({self.start_station_ord}번) → {end_station.get('stationNm')}({self.end_station_ord}번)")
            return True
        else:
            if not start_matches:
                logging.error(f"출발 정류장을 찾을 수 없음: {self.start_station}")
            if not end_matches:
                logging.error(f"도착 정류장을 찾을 수 없음: {self.end_station}")
            return False

    def get_bus_positions(self):
        """실시간 버스 위치 정보 조회"""
        url = "http://ws.bus.go.kr/api/rest/buspos/getBusPosByRtid"
        params = {
            "serviceKey": self.api_key,
            "busRouteId": self.bus_route_id,
            "resultType": "json"
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if response.status_code == 200 and data.get('msgHeader', {}).get('headerCd') == '0':
                items = data.get('msgBody', {}).get('itemList', [])
                buses = []

                for bus in items:
                    buses.append({
                        'vehId': bus.get('vehId'),       # 차량 ID
                        'plainNo': bus.get('plainNo'),   # 차량 번호판
                        'sectOrd': int(bus.get('sectOrd', 0)),  # 현재 위치 구간 순번
                        'dataTm': bus.get('dataTm'),     # 데이터 시간
                        'stopFlag': bus.get('stopFlag')  # 정류장 정차 여부 (0: 운행중, 1: 정류장도착)
                    })

                return buses
            else:
                logging.error(f"버스 위치 조회 실패: {data.get('msgHeader', {}).get('headerMsg')}")
                return []

        except Exception as e:
            logging.error(f"버스 위치 조회 중 오류: {str(e)}")
            return []

    def track_buses(self, duration_minutes=60, interval_seconds=30):
        """
        지정된 시간 동안 버스 위치를 추적

        Parameters:
        -----------
        duration_minutes : int
            추적 지속 시간(분)
        interval_seconds : int
            위치 확인 간격(초)
        """
        if not self.start_station_ord or not self.end_station_ord:
            logging.error("추적 정류장이 설정되지 않았습니다.")
            return False

        end_time = time.time() + (duration_minutes * 60)
        iterations = 0

        try:
            while time.time() < end_time:
                iterations += 1
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                #logging.info(f"[{iterations}] 버스 위치 조회 중...")

                buses = self.get_bus_positions()
                #logging.info(f"운행 중인 버스: {len(buses)}대")

                # 각 버스의 위치 추적
                for bus in buses:
                    veh_id = bus['vehId']
                    current_ord = bus['sectOrd']
                    data_time = bus['dataTm']

                    # 버스 추적 데이터 초기화
                    if veh_id not in self.bus_tracking_data:
                        self.bus_tracking_data[veh_id] = {
                            'plainNo': bus['plainNo'],
                            'positions': []
                        }

                    # 위치 정보 추가
                    self.bus_tracking_data[veh_id]['positions'].append({
                        'ord': current_ord,
                        'time': data_time,
                        'system_time': current_time
                    })

                    # 소요 시간 계산 처리
                    self._process_travel_time(veh_id)

                # 계산된 결과 저장
                if iterations % 10 == 0 or time.time() >= end_time:
                    self._save_travel_records()

                # 다음 조회까지 대기
                time.sleep(interval_seconds)

            return True

        except KeyboardInterrupt:
            logging.info("사용자에 의해 추적이 중단되었습니다.")
            self._save_travel_records()
            return False

        except Exception as e:
            logging.error(f"버스 추적 중 오류: {str(e)}")
            self._save_travel_records()
            return False

    def _process_travel_time(self, veh_id):
        """버스별 소요 시간 계산 처리"""
        if veh_id not in self.bus_tracking_data:
            return

        positions = self.bus_tracking_data[veh_id]['positions']

        # 이미 기록된 버스는 처리하지 않음
        if any(record['veh_id'] == veh_id for record in self.travel_records):
            return

        # 출발 정류장 통과 시간 찾기
        start_passage = None
        for i, pos in enumerate(positions):
            if pos['ord'] == self.start_station_ord:
                if i+1 < len(positions) and positions[i+1]['ord'] > self.start_station_ord:
                    start_passage = pos
                    break

        # 도착 정류장 통과 시간 찾기
        end_passage = None
        if start_passage:
            start_idx = positions.index(start_passage)
            for pos in positions[start_idx+1:]:
                if pos['ord'] == self.end_station_ord:
                    end_passage = pos
                    break

        # 소요 시간 계산
        if start_passage and end_passage:
            try:
                # 날짜 시간 파싱 (형식: yyyyMMddHHmmss)
                start_time = datetime.strptime(start_passage['time'], "%Y%m%d%H%M%S")
                end_time = datetime.strptime(end_passage['time'], "%Y%m%d%H%M%S")

                # 소요 시간 계산 (초)
                travel_time_seconds = (end_time - start_time).total_seconds()
                travel_time_minutes = travel_time_seconds / 60

                # 기록 추가
                record = {
                    'date': start_time.strftime("%Y-%m-%d"),
                    'day_of_week': start_time.strftime("%a"),
                    'veh_id': veh_id,
                    'plainNo': self.bus_tracking_data[veh_id]['plainNo'],
                    'start_station': self.start_station,
                    'end_station': self.end_station,
                    'start_time': start_time.strftime("%H:%M:%S"),
                    'end_time': end_time.strftime("%H:%M:%S"),
                    'travel_time_minutes': round(travel_time_minutes, 2),
                    'travel_time_seconds': int(travel_time_seconds)
                }

                self.travel_records.append(record)
                logging.info(f"새로운 소요 시간 기록: 버스 {record['plainNo']}, {record['start_time']} → {record['end_time']}, "
                             f"소요 시간: {record['travel_time_minutes']:.2f}분")

            except Exception as e:
                logging.error(f"소요 시간 계산 중 오류: {str(e)}")

    def _save_travel_records(self):
        """계산된 여행 시간 기록을 CSV 파일로 저장"""
        if not self.travel_records:
            logging.info("저장할 소요 시간 기록이 없습니다.")
            return

        try:
            df = pd.DataFrame(self.travel_records)
            df.to_csv(self.data_filename, index=False)
            logging.info(f"소요 시간 기록 {len(self.travel_records)}개를 {self.data_filename}에 저장했습니다.")

        except Exception as e:
            logging.error(f"소요 시간 기록 저장 중 오류: {str(e)}")

    def compare_with_prediction(self, time_predictions):
        """
        실제 소요 시간과 시간대별 예측 소요 시간 비교 분석
    
        Parameters:
        -----------
        time_predictions : dict
            시간대별 예측 소요 시간 (예: {'16:10': 16, '16:20': 15})
        """
        if not self.travel_records:
            logging.warning("비교할 소요 시간 기록이 없습니다.")
            return None
        
        results = []
    
        for record in self.travel_records:
            # 출발 시간 추출
            start_time_obj = datetime.strptime(record['start_time'], "%H:%M:%S")
            start_time_str = start_time_obj.strftime("%H:%M")
        
            # 해당 시간대의 예측 시간 찾기
            predicted_time = self._find_matching_prediction(start_time_str, time_predictions)
        
            # 디버깅을 위한 로그 추가
            logging.info(f"시간 {start_time_str}에 대한 예측 시간: {predicted_time}")
        
            if predicted_time is not None:
                difference = record['travel_time_minutes'] - predicted_time
                percentage = (difference / predicted_time) * 100
            
                results.append({
                'date': record['date'],
                'day_of_week': record['day_of_week'],
                'start_time': record['start_time'],
                'predicted_time': predicted_time,
                'actual_time': record['travel_time_minutes'],
                'difference_minutes': round(difference, 2),
                'percentage_difference': round(percentage, 2)
                })
            else:
                # 예측 시간을 찾지 못한 경우에도 로그 남기기
                logging.warning(f"시간 {start_time_str}에 대한 예측 시간을 찾을 수 없음")
    
        if not results:
            logging.warning("비교 가능한 기록이 없습니다.")
            return None, None
    
        results_df = pd.DataFrame(results)
    
        # 기본 통계
        avg_difference = results_df['difference_minutes'].mean()
        std_difference = results_df['difference_minutes'].std()
        max_difference = results_df['difference_minutes'].max()
        min_difference = results_df['difference_minutes'].min()
    
        summary = {
            'avg_difference': round(avg_difference, 2),
            'std_difference': round(std_difference, 2),
            'max_difference': round(max_difference, 2),
            'min_difference': round(min_difference, 2),
            'records_count': len(results)
        }
    
        logging.info(f"예측 소요 시간과의 비교 분석:")
        logging.info(f"평균 오차: {summary['avg_difference']}분")
        logging.info(f"표준편차: {summary['std_difference']}분")
        logging.info(f"최대 오차: {summary['max_difference']}분")
        logging.info(f"최소 오차: {summary['min_difference']}분")
    
        # 결과와 요약 저장
        results_df.to_csv(f"bus/data/comparison_{self.bus_route_name}.csv", index=False)
    
        with open(f"summary_{self.bus_route_name}.json", 'w') as f:
            json.dump(summary, f)
    
        return summary, results_df

    def _find_matching_prediction(self, start_time, time_predictions):
        """
        주어진 출발 시간에 맞는 예측 시간 찾기
    
        Parameters:
        -----------
        start_time : str
            출발 시간 (형식: "HH:MM")
        time_predictions : dict
            시간대별 예측 소요 시간
        
        Returns:
        --------
        float or None
            해당 시간대의 예측 소요 시간, 없으면 None
        """
        # 정확히 일치하는 시간이 있는 경우
        if start_time in time_predictions:
            logging.debug(f"정확히 일치하는 시간 발견: {start_time}")
            return time_predictions[start_time]
    
        # 시간 범위로 지정된 경우 (예: "18:00-18:20")
        for time_range, predicted_time in time_predictions.items():
            if '-' in time_range:
                start_range, end_range = time_range.split('-')
                
                # 디버깅 로그
                logging.debug(f"범위 검사: {start_range} - {end_range}")
                
                # 시간 형식을 datetime 객체로 변환하여 비교
                try:
                    time_obj = datetime.strptime(start_time, "%H:%M")
                    start_range_obj = datetime.strptime(start_range, "%H:%M")
                    end_range_obj = datetime.strptime(end_range, "%H:%M")
                    
                    if start_range_obj <= time_obj <= end_range_obj:
                        logging.debug(f"범위 내 시간 발견: {start_time} in {time_range}")
                        return predicted_time
                except ValueError as e:
                    logging.error(f"시간 형식 에러: {e}")
                    continue
    
        # 가장 가까운 시간대 찾기
        try:
            time_obj = datetime.strptime(start_time, "%H:%M")
            closest_time = None
            min_diff = float('inf')
            
            for time_str in time_predictions.keys():
                if '-' in time_str:
                    # 범위인 경우 시작 시간 사용
                    time_parts = time_str.split('-')
                    comparison_time_start_str = time_parts[0]
                    comparison_time_end_str = time_parts[1]
                    comparison_time_start = datetime.strptime(comparison_time_start_str, "%H:%M")
                    comparison_time_end = datetime.strptime(comparison_time_end_str, "%H:%M")
                    time_diff_minutes_start = abs((time_obj - comparison_time_start).total_seconds() / 60)
                    time_diff_minutes_end = abs((time_obj - comparison_time_end).total_seconds() / 60)
                    time_diff_minutes = min(time_diff_minutes_start, time_diff_minutes_end)
                    
                else:
                    comparison_time_str = time_str
                    comparison_time = datetime.strptime(comparison_time_str, "%H:%M")
                
                    # 시간 차이를 분 단위로 계산
                    time_diff_minutes = abs((time_obj - comparison_time).total_seconds() / 60)
                
                if time_diff_minutes < min_diff:
                    min_diff = time_diff_minutes
                    closest_time = time_str
            
            if closest_time:
                logging.debug(f"가장 가까운 시간 발견: {closest_time}, 차이: {min_diff}분")
                return time_predictions[closest_time]
            else:
                logging.warning("가장 가까운 시간을 찾을 수 없음")
        except Exception as e:
            logging.error(f"가장 가까운 예측 시간 찾기 실패: {str(e)}")
        
        return None

# 사용 예시
if __name__ == "__main__":
    # 공공데이터포털 API 키 입력
    API_KEY = ""
    # 데이터 수집기 초기화
    collector = BusDataCollector(
        api_key=API_KEY,
        bus_route_name="271",  # 추적할 버스 노선
        start_station="광화문역",  # 출발 정류장
        end_station="홍대입구역"     # 도착 정류장
    )

    # 버스 추적 (duration_minutes(분) 동안 interval_seconds(초) 간격으로)
    collector.track_buses(duration_minutes=1, interval_seconds=30)

    # 네이버 지도 시간대별 예상 소요 시간 (분 단위)
    time_predictions = {
      '18:00': 24,
      '18:10': 24,
      '18:20': 24,
      '18:30': 24, 
      '18:40': 23,
      '18:50': 23,
      '19:00': 23
    }


    # 네이버 지도 예상 소요 시간과 비교 (분 단위)
    collector.compare_with_prediction(time_predictions)