import os
import logging
import json
import pandas as pd
from datetime import datetime

#with open(f"summary_{self.bus_route_name}.json", 'w') as f:
#            json.dump(summary, f)

# 데이터 저장 디렉토리 생성
os.makedirs("bus/data", exist_ok=True)

def compare_with_prediction(bus_route_name, travel_records, time_predictions):
    """
    실제 소요 시간과 시간대별 예측 소요 시간 비교 분석

    Parameters:
    -----------
    time_predictions : dict
        시간대별 예측 소요 시간 (예: {'16:10': 16, '16:20': 15})
    """
    if not travel_records:
        logging.warning("비교할 소요 시간 기록이 없습니다.")
        return None
    
    results = []

    for record in travel_records:
        # 출발 시간 추출
        start_time_obj = datetime.strptime(record['start_time'], "%H:%M:%S")
        start_time_str = start_time_obj.strftime("%H:%M")
    
        # 해당 시간대의 예측 시간 찾기
        predicted_time = _find_matching_prediction(start_time_str, time_predictions)
    
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
    results_df.to_csv(f"bus/data/comparison_{bus_route_name}.csv", index=False)

    with open(f"summary_{bus_route_name}.json", 'w') as f:
        json.dump(summary, f)

    return summary, results_df

def _find_matching_prediction(start_time, time_predictions):
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

def main():
    bus_route_name = "271"
    track_file = f"bus/data/bus_{bus_route_name}_data.csv"
    summary_file = f"bus/data/bus_{bus_route_name}_summary.json"

    time_predictions={
            '8:00-10:00': 21
        }

    with open(track_file, 'r') as f:
        lines = f.readlines()

    travel_records = []
    
    for line in lines[1:]:
        values = line.strip().split(',')
        travel_records.append({
            'date': values[0],
            'day_of_week': values[1],
            'veh_id': values[2],
            'plainNo': values[3],
            'start_station': values[4],
            'end_station': values[5],
            'start_time': values[6],
            'end_time': values[7],
            'travel_time_minutes': float(''.join(values[8].split(' '))),
            'travel_time_seconds': int(values[9])
        })

    summary, _ = compare_with_prediction(
        bus_route_name=bus_route_name,
        travel_records=travel_records,
        time_predictions=time_predictions
    )
    
    # 결과 요약 출력
    print("\n=== 경로 예측 소요 시간과의 비교 결과 ===")
        
            
    #print(f"\n{travel_records['bus_route_name']}번 버스 ({travel_records['start_station']} → {travel_records['end_station']})")
    print(f"- 평균 오차: {summary.get('avg_difference', 'N/A')}분")
    print(f"- 표준편차: {summary.get('std_difference', 'N/A')}분")
    print(f"- 최대 오차: {summary.get('max_difference', 'N/A')}분")
    print(f"- 최소 오차: {summary.get('min_difference', 'N/A')}분")
    print(f"- 추적 기록 수: {summary.get('records_count', 0)}개")

    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    main()