from utility import read_csv, datetime, ChannelType, sleep, initialize_avanza
import asyncio
import backoff
import websockets
import redis
import os
import csv
from threading import Lock

base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
avanza = initialize_avanza()

# Setup Redis connection
redis_client = redis.Redis(host='localhost', port=6379, db=0)

csv_file_path = os.path.join(base_path, 'input', f'realtime_data_{datetime.now().strftime("%Y-%m-%d")}_data.csv')
csv_lock = Lock()

def init_csv():
    # Create the CSV file with headers if it does not exist
    if not os.path.exists(csv_file_path):
        with open(csv_file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Orderbook ID', 'Buy Price', 'Sell Price', 'Updated Datetime'])

def write_to_csv(data):
    with csv_lock, open(csv_file_path, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(data)

def callback(data):
    try:
        orderbook_id = data['data']['orderbookId']
        buy_price = str(data['data']['buyPrice'])
        sell_price = str(data['data']['sellPrice'])
        updated_timestamp = data['data']['updated']
        updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0).strftime('%Y-%m-%d %H:%M:%S')

        csv_data = [orderbook_id, buy_price, sell_price, updated_datetime]

        redis_client.hset(orderbook_id, mapping={
            'buyPrice': buy_price,
            'sellPrice': sell_price,
            'updated': updated_datetime
        })

        write_to_csv(csv_data)
    except Exception as e:
        print(f"Error during data callback: {e}")

@backoff.on_exception(backoff.expo, websockets.exceptions.ConnectionClosedError, max_tries=8)
async def resilient_subscribe(avanza, whitelisted_tickers):
    await subscribe_to_channel(avanza, whitelisted_tickers)

async def subscribe_to_channel(avanza, whitelisted_tickers):
    for _, id in whitelisted_tickers.items():
        try:
            await avanza.subscribe_to_id(ChannelType.QUOTES, str(id), callback)
        except Exception as e:
            print(f"Error subscribing to channel: {e}")

def main(avanza):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        stocks = read_csv(f'{base_path}/input/best_tickers.csv')
        whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))
        loop.run_until_complete(resilient_subscribe(avanza, whitelisted_tickers))

        loop.run_forever()
    except Exception as e:
        print(f"Error in main: {e}")
        sleep(2)
    finally:
        loop.close()

if __name__ == '__main__':
    init_csv()
    main(avanza)
