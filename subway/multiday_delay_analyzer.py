import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import warnings
import json
import pickle
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from subway_delay_analyzer import SubwayDelayAnalyzer

warnings.filterwarnings('ignore')

plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

def convert_numpy(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)  # 예외 fallback

class MultiDaySubwayDelayAnalyzer(SubwayDelayAnalyzer):
    def __init__(self):
        super().__init__()

    def analyze_multiday_line_delays (self, dates, time_of_day, target_line, updnLine=None, express_code=None):
        multiday_matched_data = []
        multiday_train_timeseries = defaultdict(list)
        print(f"===== {target_line}호선 지연 분석 시작 =====")

        for date in dates:
            print(f"=== {date} 지연 분석 시작 ===")
            delay_path = f"data/{date}/delay_{date}_{time_of_day}.csv"
            print("1. 데이터 로딩...")
            delay = self.load_delay_data(delay_path)
        
            print("2. 노선 데이터 필터링...")
            delay_filtered = self.filter_by_line(delay, target_line, updnLine, express_code)
            print(f"   - 실시간 데이터: {len(delay_filtered)}개 레코드")

            # 3. 데이터 매칭
            print("3. 시간표-실시간 데이터 매칭...")
            matched_data = self.match_train_data(delay_filtered, date)
            print(f"   - 매칭된 데이터: {len(matched_data)}개 레코드")

            # 4. 지연 시계열 생성
            print("4. 지연 시계열 생성...")
            train_timeseries = self.generate_delay_timeseries(matched_data)
            print(f"   - 분석된 열차 수: {len(train_timeseries)}개")

            multiday_matched_data.append(matched_data)
            for key, value in train_timeseries.items():
                multiday_train_timeseries[key] = value
                #multiday_train_timeseries[key].extend(value)

        print("\n===== {date} 분석 결과 요약 =====")
        total_delays = []
        patterns = defaultdict(int)
        
        for train_no, data in multiday_train_timeseries.items():
            avg_delay = np.mean(data['delays'])
            total_delays.append(avg_delay)
            patterns[data['cumulative_pattern']] += 1
            
        print(f"평균 지연 시간: {np.mean(total_delays):.1f}초")
        print(f"최대 지연 시간: {np.max(total_delays):.1f}초")
        print(f"지연 패턴 분포:")
        for pattern, count in patterns.items():
            print(f"  - {pattern}: {count}개 열차 ({count/len(multiday_train_timeseries)*100:.1f}%)")

        return multiday_matched_data, multiday_train_timeseries
    


if __name__ == "__main__":
    multiday_analyzer = MultiDaySubwayDelayAnalyzer()

    dates = ["0526", "0528", "0529", "0530", "0602","0603", "0604", "0605","0606", "0609", "0610"]
    time_of_day = "morning"
    target_line = "1호선"
    updnLine = "상행"
    express_code = 0  # 필요 시 지정
    start_station = '노량진'
    end_station = '신설동'

    multiday_matched_data, multiday_train_timeseries = multiday_analyzer.analyze_multiday_line_delays(
        dates=dates,
        time_of_day=time_of_day,
        target_line=target_line,
        updnLine=updnLine,  
        express_code=express_code
    )

    if multiday_train_timeseries:
        filename = f'train_timeseries_{dates}_{time_of_day}_{target_line}_{updnLine}'
        # 지연 시계열 데이터 저장
        multiday_analyzer.save_timeseries_data(multiday_train_timeseries, multiday_matched_data, save_format='json', filename=filename)
        # 저장된 데이터 로드
        loaded_timeseries, metadata = multiday_analyzer.load_timeseries_data(f"{filename}.json", load_format='json')
        # 구간별 분석 및 시각화 (예: 노량진 -> 동묘앞)
        #fig = multiday_analyzer.visualize_station_range_delays(multiday_train_timeseries, start_station, end_station)
        plt.show()
        # 구간별 통계 요약
        #summary = multiday_analyzer.generate_station_delay_summary(multiday_train_timeseries, start_station, end_station)
        #print("\n=== 구간별 통계 요약 ===")
        #if summary is not None:
        #    print(json.dumps(summary, ensure_ascii=False, indent=2, default=convert_numpy))
        #else:
        #    print("summary가 None입니다.")

        # 구간별 분석 및 시각화 (예: 노량진 -> 동묘앞)
        fig = multiday_analyzer.visualize_station_range_delays(multiday_train_timeseries, start_station, end_station)
        plt.show()

        results, figures = multiday_analyzer.comprehensive_accumulation_analysis(loaded_timeseries, start_station, end_station, False)

        # 구간별 통계 요약
        summary = multiday_analyzer.generate_station_delay_summary(multiday_train_timeseries, start_station, end_station)
        print("\n=== 구간별 통계 요약 ===")
        if summary is not None:
            print(json.dumps(summary, ensure_ascii=False, indent=2, default=convert_numpy))
        else:
            print("summary가 None입니다.")



        for i, fig in enumerate(figures, 1):
            if fig is not None:
                plt.figure(i)
                plt.show()

        