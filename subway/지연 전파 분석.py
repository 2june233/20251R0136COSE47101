
def analyze_transfer_delay(date, time_of_day, 기준호선, 기준역, 환승호선, 상행역들, 하행역들, 분석_범위_분=30):
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns
    from datetime import timedelta
    import matplotlib.font_manager as fm
    import matplotlib as mpl
    from pathlib import Path

    csv_path = Path(f"data/{date}/asof_delay_{date}_{time_of_day}.csv")
    if not csv_path.exists():
        print(f"❌ 파일이 존재하지 않습니다: {csv_path}")
        return

    # 📌 폰트 설정
    font_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
    fm.fontManager.addfont(font_path)
    plt.rcParams['font.family'] = 'NanumGothic'
    mpl.rcParams['axes.unicode_minus'] = False

    # 📁 데이터 로드 및 전처리
    df = pd.read_csv(csv_path, parse_dates=["예정시간", "실제시간"])
    df['호선'] = df['호선'].astype(str)
    df['역사명'] = df['역사명'].str.strip()
    df['지연시간(분)'] = df['지연시간(분)'].fillna(0)

    # ✅ 기준 열차 필터링 (가장 많이 지연된 열차)
    delay_train = df[
        (df['호선'] == str(기준호선)) &
        (df['역사명'] == 기준역.strip())
    ].sort_values('지연시간(분)', ascending=False)

    if delay_train.empty:
        print("❌ 지정된 기준역에서 지연 열차가 없습니다.")
        return

    # 🎯 기준 열차 정보
    target_train = delay_train.iloc[0]
    delay_train_num = int(target_train['sched_train']) if 'sched_train' in target_train else int(target_train['real_train'])
    delay_train_time = pd.to_datetime(target_train['실제시간'])
    delay_minutes = round(target_train['지연시간(분)'], 2)

    # 🔄 기준 열차 이후 일정 시간 내 환승 호선 열차 필터링
    end_time = delay_train_time + timedelta(minutes=분석_범위_분)
    df_transit = df[
        (df['호선'] == str(환승호선)) &
        (df['예정시간'] > delay_train_time) &
        (df['예정시간'] <= end_time)
    ]

    # 상·하행 필터
    upward_filtered = df_transit[
        (df_transit['방향'] == 'UP') &
        (df_transit['역사명'].isin(상행역들))
    ]
    downward_filtered = df_transit[
        (df_transit['방향'] == 'DOWN') &
        (df_transit['역사명'].isin(하행역들))
    ]

    # 📊 평균 지연 계산
    up_avg = upward_filtered.groupby('역사명')['지연시간(분)'].mean().reindex(상행역들).fillna(0)
    down_avg = downward_filtered.groupby('역사명')['지연시간(분)'].mean().reindex(하행역들).fillna(0)

    # 📈 시각화
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

    axes[0].bar(up_avg.index, up_avg.values, color='tab:blue')
    axes[0].set_title(f"상행 ({' → '.join(상행역들)})")
    axes[0].set_ylabel("평균 지연 시간 (분)")
    axes[0].grid(axis='y')

    axes[1].bar(down_avg.index, down_avg.values, color='tab:orange')
    axes[1].set_title(f"하행 ({' → '.join(하행역들)})")
    axes[1].grid(axis='y')

    delay_time_str = delay_train_time.strftime("%H:%M")
    plt.suptitle(
        f"{환승호선}호선 상·하행 평균 지연 시간 (기준 이후 {분석_범위_분}분간)\n"
        f"기준: {기준호선}호선 {기준역}역 {delay_train_num}번 열차 지연: {delay_minutes}분, 도착시간 {delay_time_str}",
        fontsize=14
    )
    plt.tight_layout(rect=[0, 0.03, 1, 0.88])
    plt.show()
'''
analyze_transfer_delay(
    date="0531",
    time_of_day="afternoon",
    기준호선=3,
    기준역='약수',
    환승호선=6,
    상행역들=['약수', '청구', '신당'],
    하행역들=['약수', '버티고개', '한강진'],
)
'''

analyze_transfer_delay(
    date="0531",
    time_of_day="afternoon",
    기준호선=1,
    기준역='가산디지털단지',
    환승호선=7,
    상행역들=['가산디지털단지', '남구로', '대림'],
    하행역들=['가산디지털단지', '철산', '광명사거리']
)
