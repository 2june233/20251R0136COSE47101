import threading
import pandas as pd
from datetime import datetime
import logging
import json
import os
from concurrent.futures import ThreadPoolExecutor

from bus_data_collector import BusDataCollector

class MultiBusTracker:
    """
    여러 경로를 동시에 추적하는 다중 경로 버스 추적기
    """
    def __init__(self, api_key):
        """
        다중 경로 버스 추적기 초기화
        
        Parameters:
        -----------
        api_key : str
            서울 열린데이터광장 API 키
        """
        self.api_key = api_key
        self.collectors = {}  # 경로별 데이터 수집기
        self.summary_data = {}  # 종합 분석 결과
        
        # 결과 저장 폴더 생성
        os.makedirs("bus/data/multi_route", exist_ok=True)
        
        # 로깅 설정
        self.setup_logging()
    
    def setup_logging(self):
        """로깅 설정"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("bus/data/multi_route/multi_tracker.log", mode='a'),
                logging.StreamHandler()
            ]
        )
    
    def add_route(self, route_id, bus_route_name, start_station, end_station, time_predictions=None):
        """
        추적할 경로 추가
        
        Parameters:
        -----------
        route_id : str
            경로 식별자 (임의의 고유 문자열)
        bus_route_name : str
            버스 노선명
        start_station : str
            출발 정류장명
        end_station : str
            도착 정류장명
        time_predictions : dict
            시간대별 예측 소요 시간 (예: {'16:10': 16, '16:20': 15})
        """
        # 경로 ID 중복 검사
        if route_id in self.collectors:
            logging.warning(f"이미 존재하는 경로 ID: {route_id}")
            return False
        
        # 데이터 수집기 생성
        collector = BusDataCollector(
            api_key=self.api_key,
            bus_route_name=bus_route_name,
            start_station=start_station,
            end_station=end_station
        )
        
        # 시간대별 예측 추가
        self.collectors[route_id] = {
            'collector': collector,
            'bus_route_name': bus_route_name, 
            'start_station': start_station,
            'end_station': end_station,
            'time_predictions': time_predictions or {},
            'results': None
        }
        
        logging.info(f"경로 추가: {route_id} - {bus_route_name} ({start_station} → {end_station})")
        return True
    
    def track_route(self, route_id, duration_minutes=60, interval_seconds=30):
        """
        단일 경로 추적 수행
        
        Parameters:
        -----------
        route_id : str
            추적할 경로 ID
        duration_minutes : int
            추적 지속 시간(분)
        interval_seconds : int
            위치 확인 간격(초)
        """
        if route_id not in self.collectors:
            logging.error(f"존재하지 않는 경로 ID: {route_id}")
            return False
        
        route_info = self.collectors[route_id]
        collector = route_info['collector']
        
        # 경로 추적 시작
        logging.info(f"경로 {route_id} 추적 시작: {route_info['bus_route_name']} ({route_info['start_station']} → {route_info['end_station']})")
        
        # 버스 추적 실행
        success = collector.track_buses(duration_minutes=duration_minutes, interval_seconds=interval_seconds)
        
        # 시간대별 예측과 비교 분석
        if route_info['time_predictions']:
            summary, results_df = collector.compare_with_prediction(route_info['time_predictions'])
            
            # 결과 저장
            if results_df is not None:
                route_info['results'] = results_df
                
                # 파일 저장
                results_file = f"bus/data/multi_route/{route_id}_comparison.csv"
                results_df.to_csv(results_file, index=False)
                
                # 요약 데이터 저장
                self.summary_data[route_id] = summary
                
                logging.info(f"경로 {route_id} 분석 완료: {len(results_df)} 개의 기록")
            else:
                logging.warning(f"경로 {route_id}에 대한 분석 결과가 없습니다.")
        
        return success
    
    def track_all_routes(self, duration_minutes=60, interval_seconds=30, parallel=True, max_workers=None):
        """
        모든 경로 동시 추적
        
        Parameters:
        -----------
        duration_minutes : int
            추적 지속 시간(분)
        interval_seconds : int
            위치 확인 간격(초)
        parallel : bool
            병렬 처리 여부 (True: 모든 경로 동시 추적, False: 순차 추적)
        max_workers : int
            병렬 처리 시 최대 작업자 수 (None: 자동 설정)
        """
        if not self.collectors:
            logging.error("추적할 경로가 없습니다.")
            return False
        
        route_ids = list(self.collectors.keys())
        
        if parallel:
            # 병렬 처리 (여러 경로 동시 추적)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.track_route, route_id, duration_minutes, interval_seconds): route_id 
                    for route_id in route_ids
                }
                
                # 실행 결과 확인
                results = {route_id: future.result() for future, route_id in futures.items()}
                success_count = sum(1 for result in results.values() if result)
                
                logging.info(f"병렬 추적 완료: {success_count}/{len(route_ids)} 경로 성공")
        else:
            # 순차 처리 (한 경로씩 추적)
            success_count = 0
            for route_id in route_ids:
                if self.track_route(route_id, duration_minutes, interval_seconds):
                    success_count += 1
            
            logging.info(f"순차 추적 완료: {success_count}/{len(route_ids)} 경로 성공")
        
        # 종합 분석 결과 저장
        self.save_summary()
        
        return success_count == len(route_ids)
    
    def save_summary(self):
        """종합 분석 결과 저장"""
        if not self.summary_data:
            logging.warning("저장할 종합 분석 결과가 없습니다.")
            return
        
        # 요약 데이터를 JSON 파일로 저장
        summary_file = "bus/data/multi_route/summary.json"
        with open(summary_file, 'w') as f:
            json.dump(self.summary_data, f, indent=2)
        
        # 종합 보고서 생성
        report_data = []
        for route_id, summary in self.summary_data.items():
            route_info = self.collectors[route_id]
            
            report_data.append({
                'route_id': route_id,
                'bus_route': route_info['bus_route_name'],
                'start_station': route_info['start_station'],
                'end_station': route_info['end_station'],
                'avg_difference': summary.get('avg_difference', 'N/A'),
                'std_difference': summary.get('std_difference', 'N/A'),
                'max_difference': summary.get('max_difference', 'N/A'),
                'min_difference': summary.get('min_difference', 'N/A'),
                'records_count': summary.get('records_count', 0)
            })
        
        # 보고서를 CSV 파일로 저장
        if report_data:
            report_df = pd.DataFrame(report_data)
            report_file = "bus/data/multi_route/report.csv"
            report_df.to_csv(report_file, index=False)
            
            logging.info(f"종합 보고서 저장 완료: {report_file}")
    
    def generate_combined_analysis(self):
        """모든 경로에 대한 종합 분석 보고서 생성"""
        if not self.collectors:
            logging.error("분석할 경로가 없습니다.")
            return None
        
        # 모든 결과 데이터 합치기
        all_results = []
        
        for route_id, route_info in self.collectors.items():
            if route_info.get('results') is not None:
                # 경로 정보 추가
                df = route_info['results'].copy()
                df['route_id'] = route_id
                df['bus_route'] = route_info['bus_route_name']
                df['start_station'] = route_info['start_station']
                df['end_station'] = route_info['end_station']
                
                all_results.append(df)
        
        if not all_results:
            logging.warning("종합 분석에 사용할 결과 데이터가 없습니다.")
            return None
        
        # 데이터 합치기
        combined_df = pd.concat(all_results, ignore_index=True)
        
        # 종합 데이터 저장
        combined_file = "bus/data/multi_route/combined_results.csv"
        combined_df.to_csv(combined_file, index=False)
        
        # 시간대별 평균 오차 분석
        time_analysis = combined_df.copy()
        time_analysis['hour'] = time_analysis['start_time'].str.split(':', expand=True)[0].astype(int)
        
        # 시간대별 평균 오차
        time_group = time_analysis.groupby(['hour', 'route_id']).agg({
            'difference_minutes': ['mean', 'std', 'count'],
            'percentage_difference': ['mean', 'std']
        }).reset_index()
        
        # 시간대별 분석 저장
        time_analysis_file = "bus/data/multi_route/time_analysis.csv"
        time_group.to_csv(time_analysis_file, index=False)
        
        # 경로별 분석
        route_group = time_analysis.groupby(['bus_route', 'start_station', 'end_station']).agg({
            'difference_minutes': ['mean', 'std', 'min', 'max', 'count'],
            'percentage_difference': ['mean', 'std', 'min', 'max']
        }).reset_index()
        
        # 경로별 분석 저장
        route_analysis_file = "bus/data/multi_route/route_analysis.csv"
        route_group.to_csv(route_analysis_file, index=False)
        
        logging.info(f"종합 분석 완료: {len(combined_df)} 개의 기록")
        return combined_df