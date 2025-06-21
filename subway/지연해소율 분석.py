import pandas as pd
import matplotlib.font_manager as fm
import matplotlib as mpl
import matplotlib.pyplot as plt

font_path = next((f for f in fm.findSystemFonts() if 'Nanum' in f), None)

if font_path:
    fm.fontManager.addfont(font_path)
    font_name = fm.FontProperties(fname=font_path).get_name()
    plt.rcParams['font.family'] = font_name

mpl.rcParams['axes.unicode_minus'] = False

def load_data_for_time(date, time_of_day):
    csv_path = f'data/{date}/asof_delay_{date}_{time_of_day}.csv'
    try:
        df = pd.read_csv(csv_path)
        df['실제시간'] = pd.to_datetime(df['실제시간'], errors='coerce')
        df = df[df['real_train'].notnull() & df['지연시간(분)'].notnull()]
        df['방향'] = df['방향'].str.lower()
        df = df[~df['방향'].isin(['in', 'out'])]
        return df
    except FileNotFoundError:
        print(f"[경고] 파일 없음: {csv_path}")
        return None

def calculate_recovery_rate(df, threshold=3):
    delayed_df = df[df['지연시간(분)'] >= threshold].copy()
    recovery_records = []

    for (line, direction), group in delayed_df.groupby(['호선', '방향']):
        for train_id in group['real_train'].unique():
            train_df = df[(df['real_train'] == train_id) & (df['방향'] == direction)].sort_values(by='실제시간')
            if train_df.empty:
                continue
            max_delay_row = train_df[train_df['지연시간(분)'] >= threshold].sort_values(by='지연시간(분)', ascending=False).head(1)
            if max_delay_row.empty:
                continue
            max_time = max_delay_row.iloc[0]['실제시간']
            after_df = train_df[train_df['실제시간'] >= max_time]
            recovery = after_df[after_df['지연시간(분)'] <= 0]
            recovered = not recovery.empty
            recovery_records.append({
                '방향': direction,
                '해소 여부': recovered
            })

    recovery_df = pd.DataFrame(recovery_records)
    if recovery_df.empty:
        return None

    summary = recovery_df.groupby('방향')['해소 여부'].value_counts().unstack().fillna(0)
    summary['총 지연 열차'] = summary.sum(axis=1)
    summary['해소율(%)'] = (summary[True] / summary['총 지연 열차']) * 100
    return summary[['해소율(%)']]

def analyze_daily_recovery(date, threshold=3):
    time_labels = ['morning', 'afternoon']
    result_frames = []

    for time_of_day in time_labels:
        df = load_data_for_time(date, time_of_day)
        if df is not None:
            summary = calculate_recovery_rate(df, threshold)
            if summary is not None:
                summary.columns = pd.MultiIndex.from_product([[time_of_day], summary.columns])
                result_frames.append(summary)

    if result_frames:
        return pd.concat(result_frames, axis=1)
    else:
        return None

def analyze_multiple_days_recovery(dates, threshold=3):
    all_results = []

    for date in dates:
        print(f"[정보] {date} 처리 중...")
        daily_result = analyze_daily_recovery(date, threshold)
        if daily_result is not None:
            all_results.append(daily_result)

    if not all_results:
        print("유효한 날짜 데이터가 없습니다.")
        return

    # 방향 기준으로 정렬 통일
    combined = pd.concat(all_results)
    mean_result = combined.groupby(level=0).mean(numeric_only=True)

    # 시각화
    mean_result.plot(kind='bar', figsize=(10, 6))
    plt.title(f"주말 평균 방향별 시간대별 지연 해소율 (≥ {threshold}분 지연)")
    plt.ylabel('해소율 (%)')
    plt.xlabel('방향')
    plt.ylim(0, 100)
    plt.grid(axis='y', linestyle='--')
    plt.tight_layout()
    plt.show()

    return mean_result

# ✅ 사용 예시
#dates = ['0604', '0605', '0530', '0609','0610']
dates = ['0606', '0607']
analyze_multiple_days_recovery(dates, threshold=1)
