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
warnings.filterwarnings('ignore')

# 한글 폰트 설정
plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

class SubwayDelayAnalyzer:
    def __init__(self):
        self.subway_id_map = {
            1001: '1호선', 1002: '2호선', 1003: '3호선', 1004: '4호선',
            1005: '5호선', 1006: '6호선', 1007: '7호선', 1008: '8호선',
            1009: '9호선', 1061: '중앙선', 1063: '경의중앙선', 1065: '공항철도',
            1067: '경춘선', 1075: '수의분당선', 1077: '신분당선', 1092: '우이신설선',
            1032: 'GTX-A'
        }
        
    def load_timetable(self, timetable_path):
        """열차운행시각표 로드"""
        try:
            timetable = pd.read_csv(timetable_path, encoding='utf-8')
        except:
            timetable = pd.read_csv(timetable_path, encoding='cp949')
            
        # 시간 컬럼 처리
        timetable['열차도착시간'] = pd.to_datetime(timetable['열차도착시간'])
        timetable['열차출발시간'] = pd.to_datetime(timetable['열차출발시간'])
        
        return timetable
    
    def load_realtime_data(self, realtime_path):
        """실시간 데이터 로드"""
        try:
            realtime = pd.read_csv(realtime_path, encoding='utf-8')
        except:
            realtime = pd.read_csv(realtime_path, encoding='cp949')
            
        # 시간 컬럼 처리
        realtime['recptnDt'] = pd.to_datetime(realtime['recptnDt'])
        
        return realtime
    
    def load_delay_data(self, delay_path):
        """지연 데이터 로드"""
        try:
            delay = pd.read_csv(delay_path, encoding='utf-8')
        except:
            delay = pd.read_csv(delay_path, encoding='cp949')
        
        # 시간 컬럼 처리
        delay['예정시간'] = pd.to_datetime(delay['예정시간'])
        delay['실제시간'] = pd.to_datetime(delay['실제시간'])
        
        return delay
    
    def filter_by_line(self, delay, target_line, updnLine=None, express_code=None):
        """특정 노선 데이터 필터링"""
        # 노선 번호 매핑 (1호선 -> 1001)
        line_to_id = {v: k for k, v in self.subway_id_map.items()}
        
        if target_line in line_to_id:
            subway_id = line_to_id[target_line]
        else:
            # 숫자로 입력된 경우 (예: 2 -> 2호선)
            if isinstance(target_line, int):
                subway_id = 1000 + target_line
            else:
                raise ValueError(f"지원하지 않는 노선입니다: {target_line}")
        
        # 시간표 필터링
        delay_filtered = delay[delay['호선'] == (subway_id - 1000)].copy()

        if updnLine is not None:
  
            updn_mapping = {
                "상행": "UP", "내선": "IN",
                "하행": "DOWN", "외선": "OUT"
            }
            
            tt_dir = updn_mapping[updnLine]
            
            # timetable에서 UP/DOWN 필터
            if '방향' in delay_filtered.columns:
                delay_filtered = delay_filtered[delay_filtered['방향'] == tt_dir]

        if express_code is not None:
           
            delay_filtered = delay_filtered[delay_filtered['급행코드'] == express_code]
        
        return delay_filtered
    
    def match_train_data(self, asof_delay, date):
        """열차 데이터 매칭 (시간표 vs 실시간)"""
        
            
        # 호선,방향,역사명,급행코드,sched_train,real_train,예정시간,실제시간,지연시간(분)
        # 이 중에서 sched_train 열을 제거
        # 지연시간 계산 안된 행은 제거
        # 지연시간 (분) -> 지연시간 (초)로 변환
        asof_delay = asof_delay.drop(columns=['sched_train'], errors='ignore')
        asof_delay = asof_delay.dropna(subset=['지연시간(분)'])
        asof_delay['delay_seconds'] = asof_delay['지연시간(분)'] * 60
        asof_delay = asof_delay.drop(columns=['지연시간(분)'], errors='ignore')
        asof_delay = asof_delay.rename(columns={
            '호선': 'line_no', '방향': 'direction', '역사명': 'station_name',
            '급행코드': 'express_code', '예정시간': 'scheduled_time',
            '실제시간': 'actual_time', 'delay_seconds': 'delay_seconds', 'real_train': 'train_no'
        })
        # train_no 열의 타입이 float이면 int로 변환 후 str로 변환
        if asof_delay['train_no'].dtype == 'float64':
            asof_delay['train_no'] = asof_delay['train_no'].astype(int).astype(str)

        # train_no 의 값 앞에 "{date}_"  추가
        asof_delay['train_no'] = date + '_' + asof_delay['train_no'].astype(str)

        # scheduled_time, actual_time에서 시간은 그대로, 날짜는 1999-01-01로 설정
        #asof_delay['scheduled_time'] = asof_delay['scheduled_time'].dt.floor('min')
        #asof_delay['actual_time'] = asof_delay['actual_time'].dt.floor('min')
        #asof_delay['scheduled_time'] = asof_delay['scheduled_time'].dt.time
        #asof_delay['actual_time'] = asof_delay['actual_time'].dt.time
        fixed_date = pd.to_datetime("1999-01-01")
        asof_delay['acual_time'] = asof_delay['actual_time'].apply(
            lambda dt: pd.Timestamp.combine(fixed_date, dt.time()) 
        )
        asof_delay['scheduled_time'] = asof_delay['scheduled_time'].apply(
            lambda dt: pd.Timestamp.combine(fixed_date, dt.time()) 
        )
        
        return asof_delay
    
    def generate_delay_timeseries(self, matched_data):
        """열차별 지연 시간 시계열 생성"""
        train_timeseries = {}
        # matched_data의 column 이름들 출력
        #print("Matched Data Columns:", matched_data.columns.tolist())
        
        # 열차별로 그룹화
        train_groups = matched_data.groupby('train_no')
        
        for train_no, train_data in train_groups:
            # 시간순으로 정렬
            train_data = train_data.sort_values('actual_time')
            
            # 지연 시간 시계열 생성
            stations = train_data['station_name'].tolist()
            delays = train_data['delay_seconds'].tolist()
            times = train_data['actual_time'].tolist()
            
            # 지연 변화율 계산
            delay_changes = [0] + [delays[i] - delays[i-1] for i in range(1, len(delays))]
            
            train_timeseries[train_no] = {
                'stations': stations,
                'delays': delays,
                'times': times,
                'delay_changes': delay_changes,
                'direction': train_data['direction'].iloc[0],
                'cumulative_pattern': self._analyze_cumulative_pattern(delays)
            }
        
        return train_timeseries
    
    def _analyze_cumulative_pattern(self, delays):
        """지연 누적 패턴 분석"""
        if len(delays) < 2:
            return 'insufficient_data'
        
        increases = sum(1 for i in range(1, len(delays)) if delays[i] > delays[i-1])
        decreases = sum(1 for i in range(1, len(delays)) if delays[i] < delays[i-1])
        
        if increases > decreases * 1.5:
            return 'cumulative'
        elif decreases > increases * 1.5:
            return 'recovering'
        else:
            return 'mixed'
    
    def visualize_train_delays(self, train_timeseries, max_trains=10):
        """열차별 지연 시간 시각화"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        
        # 1. 개별 열차 지연 시계열 (상위 N개 열차)
        ax1 = axes[0, 0]
        train_list = list(train_timeseries.items())[:max_trains]
        
        for train_no, data in train_list:
            stations_num = list(range(len(data['stations'])))
            ax1.plot(stations_num, data['delays'], marker='o', label=f'Train {train_no}', alpha=0.7)
        
        ax1.set_xlabel('Station Sequence')
        ax1.set_ylabel('Delay (seconds)')
        ax1.set_title('Individual Train Delay Timeseries')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 2. 지연 변화율 분포
        ax2 = axes[0, 1]
        all_changes = []
        for data in train_timeseries.values():
            all_changes.extend(data['delay_changes'][1:])  # 첫 번째 0 제외
        
        ax2.hist(all_changes, bins=30, alpha=0.7, edgecolor='black')
        ax2.axvline(x=0, color='red', linestyle='--', label='No Change')
        ax2.set_xlabel('Delay Change (seconds)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Distribution of Delay Changes')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # 3. 누적 패턴 분류
        ax3 = axes[1, 0]
        pattern_counts = defaultdict(int)
        for data in train_timeseries.values():
            pattern_counts[data['cumulative_pattern']] += 1
        
        patterns = list(pattern_counts.keys())
        counts = list(pattern_counts.values())
        colors = ['red', 'green', 'orange', 'blue']
        
        ax3.pie(counts, labels=patterns, autopct='%1.1f%%', colors=colors[:len(patterns)])
        ax3.set_title('Cumulative Pattern Distribution')
        
        # 4. 평균 지연 시간 vs 역 순서
        ax4 = axes[1, 1]
        max_stations = max(len(data['stations']) for data in train_timeseries.values())
        
        avg_delays_by_station = []
        for station_idx in range(max_stations):
            station_delays = []
            for data in train_timeseries.values():
                if station_idx < len(data['delays']):
                    station_delays.append(data['delays'][station_idx])
            
            if station_delays:
                avg_delays_by_station.append(np.mean(station_delays))
            else:
                avg_delays_by_station.append(0)
        
        ax4.plot(range(len(avg_delays_by_station)), avg_delays_by_station, 
                marker='o', linewidth=2, markersize=6)
        ax4.set_xlabel('Station Sequence')
        ax4.set_ylabel('Average Delay (seconds)')
        ax4.set_title('Average Delay by Station Sequence')
        ax4.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def create_delay_heatmap(self, train_timeseries):
        """지연 시간 히트맵 생성"""
        # 시간대별 지연 패턴 분석을 위한 데이터 준비
        hourly_delays = defaultdict(list)
        
        for train_no, data in train_timeseries.items():
            for i, time in enumerate(data['times']):
                hour = time.hour
                delay = data['delays'][i]
                hourly_delays[hour].append(delay)
        
        # 히트맵 데이터 생성
        hours = sorted(hourly_delays.keys())
        avg_delays = [np.mean(hourly_delays[hour]) if hourly_delays[hour] else 0 for hour in hours]
        
        fig, ax = plt.subplots(1, 1, figsize=(12, 6))
        
        # 히트맵 데이터를 2D 배열로 변환
        heatmap_data = np.array(avg_delays).reshape(1, -1)
        
        im = ax.imshow(heatmap_data, cmap='Reds', aspect='auto')
        
        # 축 설정
        ax.set_xticks(range(len(hours)))
        ax.set_xticklabels([f'{hour:02d}:00' for hour in hours])
        ax.set_yticks([0])
        ax.set_yticklabels(['Average Delay'])
        
        # 컬러바 추가
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Delay (seconds)')
        
        # 값 표시
        for i in range(len(hours)):
            ax.text(i, 0, f'{avg_delays[i]:.0f}s', 
                   ha='center', va='center', color='white' if avg_delays[i] > max(avg_delays)/2 else 'black')
        
        ax.set_title('Average Delay by Hour')
        plt.tight_layout()
        
        return fig
    
    def analyze_line_delays(self, date, delay_path, target_line, updnLine, express_code):
        """전체 분석 파이프라인 실행"""
        print(f"=== {target_line} 지연 분석 시작 ===")
        
        # 1. 데이터 로드
        print("1. 데이터 로딩...")
        delay = self.load_delay_data(delay_path)
        
        # 2. 노선별 필터링
        print("2. 노선 데이터 필터링...")
        delay_filtered = self.filter_by_line(delay, target_line, updnLine, express_code)
        print(f"   - 실시간 데이터: {len(delay_filtered)}개 레코드")
        
        # 3. 데이터 매칭
        print("3. 시간표-실시간 데이터 매칭...")
        matched_data = self.match_train_data(delay_filtered, date)
        print(f"   - 매칭된 데이터: {len(matched_data)}개 레코드")
        
        if len(matched_data) == 0:
            print("매칭된 데이터가 없습니다. 시간 허용범위를 늘려보세요.")
            return None, None
        
        # 4. 지연 시계열 생성
        print("4. 지연 시계열 생성...")
        train_timeseries = self.generate_delay_timeseries(matched_data)
        print(f"   - 분석된 열차 수: {len(train_timeseries)}개")
        
        # 5. 결과 요약
        print("\n=== 분석 결과 요약 ===")
        total_delays = []
        patterns = defaultdict(int)
        
        for train_no, data in train_timeseries.items():
            avg_delay = np.mean(data['delays'])
            total_delays.append(avg_delay)
            patterns[data['cumulative_pattern']] += 1
            
        print(f"평균 지연 시간: {np.mean(total_delays):.1f}초")
        print(f"최대 지연 시간: {np.max(total_delays):.1f}초")
        print(f"지연 패턴 분포:")
        for pattern, count in patterns.items():
            print(f"  - {pattern}: {count}개 열차 ({count/len(train_timeseries)*100:.1f}%)")
        
        return matched_data, train_timeseries
    
    def save_timeseries_data(self, train_timeseries, matched_data, save_format='json', filename=None):
        """지연 시계열 데이터 저장"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"delay_timeseries_{timestamp}"
        
        if save_format == 'json':
            # JSON 형태로 저장 (시각화 및 분석용)
            save_data = {
                'metadata': {
                    'total_trains': len(train_timeseries),
                    'total_records': len(matched_data),
                    'analysis_time': datetime.now().isoformat(),
                    'format_version': '1.0'
                },
                'train_timeseries': {}
            }
            
            for train_no, data in train_timeseries.items():
                save_data['train_timeseries'][str(train_no)] = {
                    'stations': data['stations'],
                    'delays': data['delays'],
                    'times': [t.isoformat() for t in data['times']],
                    'delay_changes': data['delay_changes'],
                    'direction': data['direction'],
                    'cumulative_pattern': data['cumulative_pattern']
                }
            
            with open(f"{filename}.json", 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            print(f"데이터가 {filename}.json에 저장되었습니다.")
        
        elif save_format == 'pickle':
            # Pickle 형태로 저장 (Python 객체 그대로)
            save_data = {
                'train_timeseries': train_timeseries,
                'matched_data': matched_data,
                'metadata': {
                    'total_trains': len(train_timeseries),
                    'total_records': len(matched_data),
                    'analysis_time': datetime.now().isoformat()
                }
            }
            
            with open(f"{filename}.pkl", 'wb') as f:
                pickle.dump(save_data, f)
            
            print(f"데이터가 {filename}.pkl에 저장되었습니다.")
        
        elif save_format == 'csv':
            # CSV 형태로 저장 (표 형태)
            csv_data = []
            for train_no, data in train_timeseries.items():
                for i, (station, delay, time, change) in enumerate(zip(
                    data['stations'], data['delays'], data['times'], data['delay_changes']
                )):
                    csv_data.append({
                        'train_no': train_no,
                        'station_sequence': i + 1,
                        'station_name': station,
                        'direction': data['direction'],
                        'actual_time': time.isoformat(),
                        'delay_seconds': delay,
                        'delay_change': change,
                        'cumulative_pattern': data['cumulative_pattern']
                    })
            
            df = pd.DataFrame(csv_data)
            df.to_csv(f"{filename}.csv", index=False, encoding='utf-8-sig')
            print(f"데이터가 {filename}.csv에 저장되었습니다.")
        
        return filename
    
    def load_timeseries_data(self, filename, load_format='json'):
        """저장된 지연 시계열 데이터 로드"""
        if load_format == 'json':
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # JSON에서 datetime 복원
            train_timeseries = {}
            for train_no, train_data in data['train_timeseries'].items():
                train_timeseries[train_no] = {
                    'stations': train_data['stations'],
                    'delays': train_data['delays'],
                    'times': train_data['times'],  # strings
                    'times': [datetime.fromisoformat(t) for t in train_data['times']],
                    'delay_changes': train_data['delay_changes'],
                    'direction': train_data['direction'],
                    'cumulative_pattern': train_data['cumulative_pattern']
                }
            
            return train_timeseries, data['metadata']
        
        elif load_format == 'pickle':
            with open(filename, 'rb') as f:
                data = pickle.load(f)
            return data['train_timeseries'], data['metadata']
        
    def get_station_sequence(self, train_timeseries, start_station, end_station):
        """시작역과 끝역 사이의 역 순서 추출"""
        # 모든 열차의 역 순서를 분석하여 공통 경로 찾기
        station_sequences = []
        
        for train_no, data in train_timeseries.items():
            stations = data['stations']
            if start_station in stations and end_station in stations:
                start_idx = stations.index(start_station)
                end_idx = stations.index(end_station)
                
                if start_idx < end_idx:  # 정방향
                    sequence = stations[start_idx:end_idx+1]
                else:  # 역방향
                    sequence = stations[end_idx:start_idx+1][::-1]
                
                station_sequences.append(sequence)
        
        if not station_sequences:
            raise ValueError(f"'{start_station}'과 '{end_station}' 사이의 경로를 찾을 수 없습니다.")
        
        # 가장 많이 나타나는 역 순서 선택
        from collections import Counter
        sequence_counter = Counter(tuple(seq) for seq in station_sequences)
        most_common_sequence = list(sequence_counter.most_common(1)[0][0])
        
        return most_common_sequence
    
    def filter_by_station_range(self, train_timeseries, start_station, end_station):
        """시작역-끝역 구간으로 데이터 필터링"""
        target_stations = self.get_station_sequence(train_timeseries, start_station, end_station)
        filtered_timeseries = {}
        
        for train_no, data in train_timeseries.items():
            stations = data['stations']
            delays = data['delays']
            times = data['times']
            delay_changes = data['delay_changes']
            
            # 구간에 해당하는 인덱스 찾기
            filtered_indices = []
            for i, station in enumerate(stations):
                if station in target_stations:
                    filtered_indices.append(i)
            
            if len(filtered_indices) >= 2:  # 최소 2개 역 이상
                filtered_timeseries[train_no] = {
                    'stations': [stations[i] for i in filtered_indices],
                    'delays': [delays[i] for i in filtered_indices],
                    'times': [times[i] for i in filtered_indices],
                    'delay_changes': [delay_changes[i] for i in filtered_indices],
                    'direction': data['direction'],
                    'cumulative_pattern': data['cumulative_pattern']
                }
        
        return filtered_timeseries, target_stations
    
    def visualize_station_range_delays(self, train_timeseries, start_station, end_station, max_trains=15):
        """구간별 지연 시간 시각화"""
        # 구간 데이터 필터링
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries:
            print(f"'{start_station}'과 '{end_station}' 구간에 해당하는 데이터가 없습니다.")
            return None
        
        fig, axes = plt.subplots(2, 1, figsize=(16, 12))
        
        # 1. Individual Train Delay Timeseries (구간별)
        ax1 = axes[0]
        train_list = list(filtered_timeseries.items())[:max_trains]
        
        for train_no, data in train_list:
            station_positions = []
            for station in data['stations']:
                if station in target_stations:
                    station_positions.append(target_stations.index(station))
            
            ax1.plot(station_positions, data['delays'], marker='o', 
                    label=f'Train {train_no}', alpha=0.7, linewidth=1.5)
        
        ax1.set_xlabel('Station Position in Route')
        ax1.set_ylabel('Delay (seconds)')
        ax1.set_title(f'Individual Train Delays: {start_station} → {end_station}')
        ax1.set_xticks(range(len(target_stations)))
        ax1.set_xticklabels(target_stations, rotation=45, ha='right')
        ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # 2. Average Delay by Station (구간별)
        ax2 = axes[1]
        station_avg_delays = []
        station_std_delays = []
        
        for station in target_stations:
            station_delays = []
            for data in filtered_timeseries.values():
                if station in data['stations']:
                    station_idx = data['stations'].index(station)
                    station_delays.append(data['delays'][station_idx])
            
            if station_delays:
                station_avg_delays.append(np.mean(station_delays))
                station_std_delays.append(np.std(station_delays))
            else:
                station_avg_delays.append(0)
                station_std_delays.append(0)
        
        x_pos = range(len(target_stations))
        ax2.errorbar(x_pos, station_avg_delays, yerr=station_std_delays, 
                    marker='o', linewidth=2, markersize=8, capsize=5)
        ax2.set_xlabel('Station')
        ax2.set_ylabel('Average Delay (seconds)')
        ax2.set_title(f'Average Delay by Station: {start_station} → {end_station}')
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(target_stations, rotation=45, ha='right')
        ax2.grid(True, alpha=0.3)
        
        # 3. Delay Change Distribution (구간별)
        # ax3 = axes[1, 0]
        # all_changes = []
        # for data in filtered_timeseries.values():
        #     all_changes.extend(data['delay_changes'][1:])  # 첫 번째 0 제외
        
        # if all_changes:
        #     ax3.hist(all_changes, bins=25, alpha=0.7, edgecolor='black')
        #     ax3.axvline(x=0, color='red', linestyle='--', label='No Change')
        #     ax3.set_xlabel('Delay Change (seconds)')
        #     ax3.set_ylabel('Frequency')
        #     ax3.set_title(f'Delay Change Distribution: {start_station} → {end_station}')
        #     ax3.legend()
        #     ax3.grid(True, alpha=0.3)
        
        # # 4. Station-wise Delay Heatmap
        # ax4 = axes[1, 1]
        
        # # 열차별, 역별 지연 시간 매트릭스 생성
        # train_names = list(filtered_timeseries.keys())[:max_trains]
        # delay_matrix = []
        
        # for train_no in train_names:
        #     data = filtered_timeseries[train_no]
        #     train_delays = []
        #     for station in target_stations:
        #         if station in data['stations']:
        #             station_idx = data['stations'].index(station)
        #             train_delays.append(data['delays'][station_idx])
        #         else:
        #             train_delays.append(np.nan)
        #     delay_matrix.append(train_delays)
        
        # if delay_matrix:
        #     im = ax4.imshow(delay_matrix, cmap='RdYlBu_r', aspect='auto')
            
        #     ax4.set_xticks(range(len(target_stations)))
        #     ax4.set_xticklabels(target_stations, rotation=45, ha='right')
        #     ax4.set_yticks(range(len(train_names)))
        #     ax4.set_yticklabels([f'Train {t}' for t in train_names])
        #     ax4.set_title(f'Delay Heatmap: {start_station} → {end_station}')
            
        #     # 컬러바 추가
        #     cbar = plt.colorbar(im, ax=ax4)
        #     cbar.set_label('Delay (seconds)')
        
        plt.tight_layout()
        return fig
    
    def generate_station_delay_summary(self, train_timeseries, start_station, end_station):
        """구간별 지연 통계 요약 생성"""
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries:
            return None
        
        summary = {
            'route_info': {
                'start_station': start_station,
                'end_station': end_station,
                'stations_in_route': target_stations,
                'total_stations': len(target_stations),
                'analyzed_trains': len(filtered_timeseries)
            },
            'station_statistics': {}
        }
        
        # 각 역별 통계
        for station in target_stations:
            station_delays = []
            station_changes = []
            
            for data in filtered_timeseries.values():
                if station in data['stations']:
                    station_idx = data['stations'].index(station)
                    station_delays.append(data['delays'][station_idx])
                    if station_idx > 0:
                        station_changes.append(data['delay_changes'][station_idx])
            
            if station_delays:
                summary['station_statistics'][station] = {
                    'avg_delay': np.mean(station_delays),
                    'std_delay': np.std(station_delays),
                    'min_delay': np.min(station_delays),
                    'max_delay': np.max(station_delays),
                    'avg_delay_change': np.mean(station_changes) if station_changes else 0,
                    'sample_size': len(station_delays)
                }
        
        return summary
    
    def create_spatiotemporal_heatmap_delay(self, train_timeseries, start_station, end_station, time_interval_minutes=10):
        """1. 시공간 누적 히트맵"""
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries:
            print("해당 구간의 데이터가 없습니다.")
            return None
        
        # 시간 구간 생성
        all_times = []
        for data in filtered_timeseries.values():
            fixed_date = pd.to_datetime("1999-01-01")
            data["times"] = [pd.Timestamp.combine(fixed_date, t.time()) for t in data['times']]
            all_times.extend(data['times'])
        
        min_time = min(all_times)
        max_time = max(all_times)
        
        # 시간 구간별로 지연 변화율 집계
        time_bins = []
        current_time = min_time.replace(minute=(min_time.minute // time_interval_minutes) * time_interval_minutes, second=0, microsecond=0)
        while current_time <= max_time:
            time_bins.append(current_time)
            current_time += timedelta(minutes=time_interval_minutes)
        
        # 히트맵 데이터 생성
        heatmap_data = np.zeros((len(time_bins), len(target_stations)))
        count_data = np.zeros((len(time_bins), len(target_stations)))
        
        for train_no, data in filtered_timeseries.items():
            for i, (station, time, delay_change) in enumerate(zip(data['stations'], data['times'], data['delays'])):
                if station in target_stations and i > 0:  # 첫 번째 변화율(0) 제외
                    station_idx = target_stations.index(station)
                    
                    # 해당 시간이 속하는 구간 찾기
                    for t_idx, time_bin in enumerate(time_bins[:-1]):
                        if time_bin <= time < time_bins[t_idx + 1]:
                            heatmap_data[t_idx, station_idx] += delay_change
                            count_data[t_idx, station_idx] += 1
                            break
        
        # 평균 계산
        with np.errstate(divide='ignore', invalid='ignore'):
            avg_heatmap_data = np.divide(heatmap_data, count_data, out=np.zeros_like(heatmap_data), where=count_data!=0)
        
        # 시각화
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # 시간 레이블 생성
        time_labels = [t.strftime('%H:%M') for t in time_bins[:-1]]
        
        im = ax.imshow(avg_heatmap_data, cmap='RdBu_r', aspect='auto', vmin=-30, vmax=30)
        
        ax.set_xticks(range(len(target_stations)))
        ax.set_xticklabels(target_stations, rotation=45, ha='right')
        ax.set_yticks(range(len(time_labels)))
        ax.set_yticklabels(time_labels)
        ax.set_xlabel('Stations')
        ax.set_ylabel('Time Intervals')
        ax.set_title(f'Spatiotemporal Delay Accumulation Heatmap\n{start_station} → {end_station}')
        
        # 컬러바
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Average Delay (seconds)')
        
        # 값 표시 (절댓값이 10 이상인 경우만)
        for i in range(len(time_labels)):
            for j in range(len(target_stations)):
                if abs(avg_heatmap_data[i, j]) >= 10:
                    color = 'white' if abs(avg_heatmap_data[i, j]) > 20 else 'black'
                    ax.text(j, i, f'{avg_heatmap_data[i, j]:.0f}', 
                        ha='center', va='center', color=color, fontsize=8)
        
        plt.tight_layout()
        return fig, avg_heatmap_data
    
    def create_spatiotemporal_heatmap_delay_change(self, train_timeseries, start_station, end_station, time_interval_minutes=10):
        """1. 시공간 누적 히트맵"""
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries:
            print("해당 구간의 데이터가 없습니다.")
            return None
        
        # 시간 구간 생성
        all_times = []
        for data in filtered_timeseries.values():
            fixed_date = pd.to_datetime("1999-01-01")
            data["times"] = [pd.Timestamp.combine(fixed_date, t.time()) for t in data['times']]
            all_times.extend(data['times'])
        
        min_time = min(all_times)
        max_time = max(all_times)
        
        # 시간 구간별로 지연 변화율 집계
        time_bins = []
        current_time = min_time.replace(minute=(min_time.minute // time_interval_minutes) * time_interval_minutes, second=0, microsecond=0)
        while current_time <= max_time:
            time_bins.append(current_time)
            current_time += timedelta(minutes=time_interval_minutes)
        
        # 히트맵 데이터 생성
        heatmap_data = np.zeros((len(time_bins), len(target_stations)))
        count_data = np.zeros((len(time_bins), len(target_stations)))
        
        for train_no, data in filtered_timeseries.items():
            for i, (station, time, delay_change) in enumerate(zip(data['stations'], data['times'], data['delay_changes'])):
                if station in target_stations and i > 0:  # 첫 번째 변화율(0) 제외
                    station_idx = target_stations.index(station)
                    
                    # 해당 시간이 속하는 구간 찾기
                    for t_idx, time_bin in enumerate(time_bins[:-1]):
                        if time_bin <= time < time_bins[t_idx + 1]:
                            heatmap_data[t_idx, station_idx] += delay_change
                            count_data[t_idx, station_idx] += 1
                            break
        
        # 평균 계산
        with np.errstate(divide='ignore', invalid='ignore'):
            avg_heatmap_data = np.divide(heatmap_data, count_data, out=np.zeros_like(heatmap_data), where=count_data!=0)
        
        # 시각화
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # 시간 레이블 생성
        time_labels = [t.strftime('%H:%M') for t in time_bins[:-1]]
        
        im = ax.imshow(avg_heatmap_data, cmap='RdBu_r', aspect='auto', vmin=-30, vmax=30)
        
        ax.set_xticks(range(len(target_stations)))
        ax.set_xticklabels(target_stations, rotation=45, ha='right')
        ax.set_yticks(range(len(time_labels)))
        ax.set_yticklabels(time_labels)
        ax.set_xlabel('Stations')
        ax.set_ylabel('Time Intervals')
        ax.set_title(f'Spatiotemporal Delay Changes Accumulation Heatmap\n{start_station} → {end_station}')
        
        # 컬러바
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Average Delay Change (seconds)')
        
        # 값 표시 (절댓값이 10 이상인 경우만)
        for i in range(len(time_labels)):
            for j in range(len(target_stations)):
                if abs(avg_heatmap_data[i, j]) >= 10:
                    color = 'white' if abs(avg_heatmap_data[i, j]) > 20 else 'black'
                    ax.text(j, i, f'{avg_heatmap_data[i, j]:.0f}', 
                        ha='center', va='center', color=color, fontsize=8)
        
        plt.tight_layout()
        return fig, avg_heatmap_data
    
    def create_accumulation_flow_chart(self, train_timeseries, start_station, end_station):
        """2. 누적 강도 플로우 차트"""
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries or len(target_stations) < 2:
            return None
        
        # 구간별 누적/소멸 빈도 계산
        segment_stats = {}
        
        for i in range(len(target_stations) - 1):
            segment = f"{target_stations[i]} → {target_stations[i+1]}"
            accumulation_count = 0
            dissipation_count = 0
            total_change = 0
            
            for data in filtered_timeseries.values():
                stations = data['stations']
                changes = data['delay_changes']
                
                # 해당 구간의 변화율 찾기
                for j in range(len(stations) - 1):
                    if (stations[j] == target_stations[i] and 
                        j + 1 < len(stations) and stations[j + 1] == target_stations[i + 1]):
                        
                        change = changes[j + 1]
                        total_change += change
                        
                        if change > 5:  # 5초 이상 증가
                            accumulation_count += 1
                        elif change < -5:  # 5초 이상 감소
                            dissipation_count += 1
                        break
            
            total_count = accumulation_count + dissipation_count
            if total_count > 0:
                segment_stats[segment] = {
                    'accumulation_ratio': accumulation_count / total_count,
                    'dissipation_ratio': dissipation_count / total_count,
                    'avg_change': total_change / total_count if total_count > 0 else 0,
                    'total_trains': total_count
                }
        
        # 시각화
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        segments = list(segment_stats.keys())
        accumulation_ratios = [segment_stats[seg]['accumulation_ratio'] for seg in segments]
        dissipation_ratios = [segment_stats[seg]['dissipation_ratio'] for seg in segments]
        avg_changes = [segment_stats[seg]['avg_change'] for seg in segments]
        
        # 상단: 누적/소멸 비율
        x_pos = np.arange(len(segments))
        width = 0.35
        
        bars1 = ax1.bar(x_pos - width/2, accumulation_ratios, width, 
                        label='Accumulation Ratio', color='red', alpha=0.7)
        bars2 = ax1.bar(x_pos + width/2, dissipation_ratios, width,
                        label='Dissipation Ratio', color='blue', alpha=0.7)
        
        ax1.set_xlabel('Segments')
        ax1.set_ylabel('Ratio')
        ax1.set_title('Accumulation vs Dissipation Ratio by Segment')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(segments, rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 하단: 평균 변화량
        colors = ['red' if change > 0 else 'blue' for change in avg_changes]
        bars3 = ax2.bar(x_pos, avg_changes, color=colors, alpha=0.7)
        
        ax2.set_xlabel('Segments')
        ax2.set_ylabel('Average Delay Change (seconds)')
        ax2.set_title('Average Delay Change by Segment')
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(segments, rotation=45, ha='right')
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig, segment_stats
    
    def analyze_time_period_patterns(self, train_timeseries, start_station, end_station):
        """3. 시간대별 누적 패턴 분석"""
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries:
            return None
        
        # 시간대별 분류 (러시아워 기준)
        time_periods = {
            'morning_rush': (7, 10),    # 07:00-10:00
            'evening_rush': (17, 20),   # 17:00-20:00  
            'night': (21, 24)           # 21:00-24:00
        }
        
        period_analysis = {}
        
        for period_name, (start_hour, end_hour) in time_periods.items():
            period_data = {}
            
            # 해당 시간대 데이터 필터링
            period_trains = {}
            for train_no, data in filtered_timeseries.items():
                period_indices = []
                for i, time in enumerate(data['times']):
                    if start_hour <= time.hour < end_hour:
                        period_indices.append(i)
                
                if period_indices:
                    period_trains[train_no] = {
                        'stations': [data['stations'][i] for i in period_indices],
                        'delays': [data['delays'][i] for i in period_indices],
                        'delay_changes': [data['delay_changes'][i] for i in period_indices],
                        'times': [data['times'][i] for i in period_indices]
                    }
            
            # 구간별 분석
            segment_analysis = {}
            for i in range(len(target_stations) - 1):
                segment = f"{target_stations[i]}-{target_stations[i+1]}"
                changes = []
                
                for data in period_trains.values():
                    stations = data['stations']
                    delay_changes = data['delay_changes']
                    
                    for j in range(len(stations) - 1):
                        if (stations[j] == target_stations[i] and 
                            j + 1 < len(stations) and stations[j + 1] == target_stations[i + 1]):
                            changes.append(delay_changes[j + 1])
                            break
                
                if changes:
                    accumulation_pct = sum(1 for c in changes if c > 5) / len(changes) * 100
                    avg_change = np.mean(changes)
                    
                    segment_analysis[segment] = {
                        'accumulation_percentage': accumulation_pct,
                        'average_change': avg_change,
                        'sample_size': len(changes)
                    }
            
            period_analysis[period_name] = segment_analysis
        
        return period_analysis
    
    def classify_station_roles(self, train_timeseries, start_station, end_station):
        """4. 역별 누적/소멸 역할 분류"""
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries:
            return None
        
        station_roles = {}
        
        for station in target_stations:
            station_changes = []
            
            # 해당 역에서의 모든 지연 변화 수집
            for data in filtered_timeseries.values():
                if station in data['stations']:
                    station_idx = data['stations'].index(station)
                    if station_idx > 0:  # 첫 번째 역이 아닌 경우
                        station_changes.append(data['delay_changes'][station_idx])
            
            if station_changes:
                avg_change = np.mean(station_changes)
                accumulation_ratio = sum(1 for c in station_changes if c > 5) / len(station_changes)
                dissipation_ratio = sum(1 for c in station_changes if c < -5) / len(station_changes)
                
                # 역할 분류
                if accumulation_ratio > 0.6:
                    role = 'accumulation_hotspot'
                elif dissipation_ratio > 0.6:
                    role = 'dissipation_zone'
                elif abs(avg_change) < 2:
                    role = 'neutral'
                else:
                    role = 'transition_point'
                
                station_roles[station] = {
                    'role': role,
                    'avg_change': avg_change,
                    'accumulation_ratio': accumulation_ratio,
                    'dissipation_ratio': dissipation_ratio,
                    'sample_size': len(station_changes),
                    'contribution_score': avg_change * len(station_changes)  # 누적 기여도
                }
        
        # 시각화
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        stations = list(station_roles.keys())
        contribution_scores = [station_roles[s]['contribution_score'] for s in stations]
        avg_changes = [station_roles[s]['avg_change'] for s in stations]
        roles = [station_roles[s]['role'] for s in stations]
        
        # 역할별 색상 매핑
        role_colors = {
            'accumulation_hotspot': 'red',
            'dissipation_zone': 'blue', 
            'neutral': 'gray',
            'transition_point': 'orange'
        }
        colors = [role_colors[role] for role in roles]
        
        # 상단: 누적 기여도 점수
        bars1 = ax1.bar(stations, contribution_scores, color=colors, alpha=0.7)
        ax1.set_xlabel('Stations')
        ax1.set_ylabel('Contribution Score')
        ax1.set_title('Station Delay Contribution Score')
        ax1.tick_params(axis='x', rotation=45)
        ax1.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax1.grid(True, alpha=0.3)
        
        # 하단: 평균 변화량
        bars2 = ax2.bar(stations, avg_changes, color=colors, alpha=0.7)
        ax2.set_xlabel('Stations')
        ax2.set_ylabel('Average Delay Change (seconds)')
        ax2.set_title('Average Delay Change by Station')
        ax2.tick_params(axis='x', rotation=45)
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.grid(True, alpha=0.3)
        
        # 범례 추가
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=color, label=role.replace('_', ' ').title()) 
                        for role, color in role_colors.items()]
        ax1.legend(handles=legend_elements, loc='upper right')
        
        plt.tight_layout()
        return fig, station_roles
    
    def create_accumulation_trend_timeline(self, train_timeseries, start_station, end_station, window_minutes=30):
        """5. 시계열 누적 트렌드 라인"""
        filtered_timeseries, target_stations = self.filter_by_station_range(
            train_timeseries, start_station, end_station
        )
        
        if not filtered_timeseries:
            return None
        
        # 시간별 누적 압력 지수 계산
        time_accumulation = defaultdict(list)
        
        for data in filtered_timeseries.values():
            fixed_date = pd.to_datetime("1999-01-01")
            data["times"] = [pd.Timestamp.combine(fixed_date, t.time()) for t in data['times']]
            
            for time, delay_change in zip(data['times'], data['delay_changes']):
                if delay_change != 0:  # 첫 번째 0값 제외
                    time_key = time.replace(second=0, microsecond=0)
                    time_accumulation[time_key].append(delay_change)
        
        # 시간순 정렬 및 누적 압력 지수 계산
        sorted_times = sorted(time_accumulation.keys())
        accumulation_pressure = []
        
        for time in sorted_times:
            changes = time_accumulation[time]
            # 누적 압력 = (누적 변화량의 합) + (누적 빈도 가중치)
            positive_changes = [c for c in changes if c > 0]
            negative_changes = [c for c in changes if c < 0]
            
            pressure = (sum(positive_changes) - sum(negative_changes)) + len(positive_changes) * 5
            accumulation_pressure.append(pressure)
        
        # 이동평균으로 트렌드 평활화
        def moving_average(data, window):
            if len(data) < window:
                return data
            return [np.mean(data[i:i+window]) for i in range(len(data) - window + 1)]
        
        smoothed_pressure = moving_average(accumulation_pressure, min(5, len(accumulation_pressure)))
        smoothed_times = sorted_times[:len(smoothed_pressure)]
        
        # 시각화
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # 상단: 원본 누적 압력
        ax1.plot(sorted_times, accumulation_pressure, 'o-', alpha=0.6, label='Raw Pressure')
        ax1.plot(smoothed_times, smoothed_pressure, 'r-', linewidth=2, label='Smoothed Trend')
        ax1.set_ylabel('Accumulation Pressure Index')
        ax1.set_title(f'Delay Accumulation Pressure Timeline: {start_station} → {end_station}')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.axhline(y=0, color='black', linestyle='--', alpha=0.5)
        
        # 하단: 누적 vs 소멸 비율
        accumulation_ratios = []
        time_windows = []
        
        for i in range(0, len(sorted_times), 5):  # 5분 간격으로 윈도우
            window_times = sorted_times[i:i+5]
            if len(window_times) >= 3:
                window_changes = []
                for t in window_times:
                    window_changes.extend(time_accumulation[t])
                
                if window_changes:
                    acc_count = sum(1 for c in window_changes if c > 5)
                    dis_count = sum(1 for c in window_changes if c < -5)
                    total = acc_count + dis_count
                    
                    if total > 0:
                        accumulation_ratios.append(acc_count / total)
                        time_windows.append(window_times[len(window_times)//2])
        
        if time_windows:
            ax2.plot(time_windows, accumulation_ratios, 'g-o', linewidth=2)
            ax2.set_xlabel('Time')
            ax2.set_ylabel('Accumulation Ratio')
            ax2.set_title('Accumulation vs Dissipation Ratio Over Time')
            ax2.set_ylim(0, 1)
            ax2.grid(True, alpha=0.3)
            ax2.axhline(y=0.5, color='black', linestyle='--', alpha=0.5, label='Balance Line')
            ax2.legend()
        
        # X축 시간 포맷 설정
        import matplotlib.dates as mdates
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        return fig, {
            'times': sorted_times,
            'pressure': accumulation_pressure,
            'smoothed_pressure': smoothed_pressure,
            'accumulation_ratios': accumulation_ratios,
            'time_windows': time_windows
        }
    
    def comprehensive_accumulation_analysis(self, train_timeseries, start_station, end_station, save_results=True):
        """전체 누적/소멸 분석 실행"""
        print(f"=== {start_station} → {end_station} 구간 누적/소멸 분석 ===\n")
        
        results = {}
        
        # 1-1. 시공간 히트맵
        print("1-1. 시공간 지연 누적 히트맵 생성...")
        fig1, heatmap_data = self.create_spatiotemporal_heatmap_delay(train_timeseries, start_station, end_station)
        results['spatiotemporal_heatmap'] = heatmap_data

        # 1-2. 시공간 히트맵
        print("1-2. 시공간 지연 변화량 히트맵 생성...")
        fig1, heatmap_data = self.create_spatiotemporal_heatmap_delay_change(train_timeseries, start_station, end_station)
        results['spatiotemporal_heatmap'] = heatmap_data
        
        # 2. 플로우 차트
        print("2. 누적 강도 플로우 차트 생성...")
        fig2, flow_stats = self.create_accumulation_flow_chart(train_timeseries, start_station, end_station)
        results['flow_analysis'] = flow_stats
        
        # 3. 시간대별 패턴
        print("3. 시간대별 누적 패턴 분석...")
        period_patterns = self.analyze_time_period_patterns(train_timeseries, start_station, end_station)
        results['time_period_patterns'] = period_patterns
        
        # 4. 역할 분류
        print("4. 역별 누적/소멸 역할 분류...")
        fig4, station_roles = self.classify_station_roles(train_timeseries, start_station, end_station)
        results['station_roles'] = station_roles
        
        # 5. 트렌드 라인
        print("5. 누적 트렌드 타임라인 생성...")
        fig5, trend_data = self.create_accumulation_trend_timeline(train_timeseries, start_station, end_station)
        results['trend_analysis'] = trend_data
        
        # 결과 요약 출력
        print("\n=== 분석 결과 요약 ===")
        if period_patterns:
            for period, data in period_patterns.items():
                print(f"\n{period.replace('_', ' ').title()}:")
                for segment, stats in data.items():
                    print(f"  {segment}: {stats['accumulation_percentage']:.1f}% 누적 (평균 {stats['average_change']:+.1f}초)")
        
        if station_roles:
            hotspots = [s for s, info in station_roles.items() if info['role'] == 'accumulation_hotspot']
            dissipation_zones = [s for s, info in station_roles.items() if info['role'] == 'dissipation_zone']
            
            if hotspots:
                print(f"\n누적 핫스팟: {', '.join(hotspots)}")
            if dissipation_zones:
                print(f"소멸 구간: {', '.join(dissipation_zones)}")
        
        if save_results:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"accumulation_analysis_{start_station}_{end_station}_{timestamp}"
            
            import json
            with open(f"{filename}.json", 'w', encoding='utf-8') as f:
                # datetime 객체를 문자열로 변환
                serializable_results = {}
                for key, value in results.items():
                    if isinstance(value, np.ndarray):
                        serializable_results[key] = value.tolist()
                    elif key == 'trend_analysis' and 'times' in value:
                        serializable_results[key] = {
                            k: (v.tolist() if isinstance(v, np.ndarray) else 
                                [t.isoformat() for t in v] if k in ['times', 'time_windows'] else v)
                            for k, v in value.items()
                        }
                    else:
                        serializable_results[key] = value
                
                json.dump(serializable_results, f, ensure_ascii=False, indent=2)
            print(f"\n분석 결과가 {filename}.json에 저장되었습니다.")
        
        return results, [fig1, fig2, fig4, fig5]

def convert_numpy(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)  # 예외 fallback



# 사용 예시
if __name__ == "__main__":
    analyzer = SubwayDelayAnalyzer()
    
    date = '0529'
    time_of_day = 'morning'
    delay_path = f'data/{date}/delay_{date}_{time_of_day}.csv'
    target_line = '2호선'
    updnLine = '내선'  # 상행선 데이터만 분석. None 이면 전체 데이터
    express_code = 0 # 일반 열차만 분석. 1이면 급행열차만 분석. None 이면 전체 데이터
    start_station = '건대입구'
    end_station = '선릉'
    
    # 분석 실행 (예: 2호선)
    matched_data, train_timeseries = analyzer.analyze_line_delays(
        date=date,
        delay_path=delay_path, 
        target_line=target_line,
        updnLine=updnLine,  
        express_code=express_code
    )
    
    if train_timeseries:
        filename = f'train_timeseries_{date}_{time_of_day}_{target_line}_{updnLine}'
        # 지연 시계열 데이터 저장
        analyzer.save_timeseries_data(train_timeseries, matched_data, save_format='json', filename=filename)
        
        #results, figures = analyzer.comprehensive_accumulation_analysis(train_timeseries, start_station, end_station)

        #for i, fig in enumerate(figures, 1):
        #    if fig is not None:
        #        plt.figure(i)
        #        plt.show()

        loaded_timeseries, metadata = analyzer.load_timeseries_data(f"{filename}.json", load_format='json')

        # 개별 열차 상세 정보 출력
        print("\n=== 개별 열차 상세 정보 ===")
        for i, (train_no, data) in enumerate(list(loaded_timeseries.items())[:10]):
            print(f"\n열차 {train_no} ({data['direction']}):")
            for j, (station, delay, change) in enumerate(zip(data['stations'], data['delays'], data['delay_changes'])):
                print(f"  역{j+1} {station}: {delay:+.0f}초 (변화: {change:+.0f}초)")
            print(f"  패턴: {data['cumulative_pattern']}")