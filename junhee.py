import requests
import pandas as pd
import xml.etree.ElementTree as ET
import time
from datetime import datetime

API_KEYS = [
]

time_of_day = 'morning'
duration_min = 120
interval_sec = 10

today = datetime.now().strftime('%m%d')
filename = f'all_{today}_{time_of_day}.csv'
key_idx = 0

def collect_all_data(key):
    try:
        url = f'http://swopenAPI.seoul.go.kr/api/subway/{key}/xml/realtimeStationArrival/ALL'
        response = requests.get(url)
        response.encoding = 'utf-8'
        root = ET.fromstring(response.content)
        rows = root.findall('row')
    except Exception as e:
        print(f'API request failed ({e})')
        return pd.DataFrame()

    if not rows:
        print('No data received')
        return pd.DataFrame()

    records = [{child.tag: child.text for child in row} for row in rows]
    df_new = pd.DataFrame(records)
    print(f'Collected {len(records)} records using key {key}')
    return df_new

print(f'Starting {interval_sec} seconds interval data collection for {duration_min} minutes...\n')

try:
    total_rounds = (duration_min * 60) // interval_sec
    header_written = False

    for i in range(total_rounds):
        current_key = API_KEYS[key_idx]
        df_round = collect_all_data(current_key)

        if not df_round.empty:
            df_round['collected_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df_round.to_csv(
                filename,
                mode='a',
                header=not header_written,
                index=False,
                encoding='utf-8-sig'
            )
            header_written = True
        
        key_idx = (key_idx + 1) % len(API_KEYS)
        time.sleep(interval_sec)

    print(f'\nAll data collection complete. Data saved continuously to {filename}')

except KeyboardInterrupt:
    print('\nData collection interrupted by user')
