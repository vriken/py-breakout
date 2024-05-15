import websockets
from pathlib import Path
from datetime import datetime
import logging
import backoff
import websockets.exceptions

base_path = Path(__file__).parents[2]


def callback(data):
    try:
        orderbook_id = data['data']['orderbookId']
        buy_price = str(data['data']['buyPrice'])
         sell_price = str(data['data']['sellPrice'])
        updated_timestamp = data['data']['updated']
        updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(e)