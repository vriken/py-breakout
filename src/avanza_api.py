from utility import read_csv, datetime, ChannelType, sleep
import asyncio
import backoff
import websockets

# Callback function to process data received from the subscription
def callback(data):
    try:
        current_date = datetime.now().strftime("%Y-%m-%d")
        orderbook_id = data['data']['orderbookId']
        buy_price = data['data']['buyPrice']
        sell_price = data['data']['sellPrice']
        updated_timestamp = data['data']['updated']
        updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0)
        file_path = f"/Users/ake/Documents/probable_spoon_a/input/realtime_data_{current_date}_data.csv"
        with open(file_path, 'a') as file:
            file.write(f"{orderbook_id}, {buy_price}, {sell_price}, {updated_datetime}\n")
    except Exception:
        pass  # Optional: handle exceptions silently or log them if necessary

# Define a backoff strategy for subscribing to channels
@backoff.on_exception(backoff.expo, websockets.exceptions.ConnectionClosedError, max_tries=8)
async def resilient_subscribe(avanza, whitelisted_tickers):
    await subscribe_to_channel(avanza, whitelisted_tickers)

# Function to subscribe to channels based on the whitelisted tickers
async def subscribe_to_channel(avanza, whitelisted_tickers):
    for _, id in whitelisted_tickers.items():
        try:
            await avanza.subscribe_to_id(ChannelType.QUOTES, str(id), callback)
        except Exception:
            pass  # Optional: handle exceptions silently or log them if necessary

def main(avanza):
    try:
        stocks = read_csv('/Users/ake/Documents/probable_spoon_a/input/best_tickers.csv')
        whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))
        loop = asyncio.get_event_loop()
        loop.run_until_complete(resilient_subscribe(avanza, whitelisted_tickers))
        loop.run_forever()
    except Exception:
        sleep(2)  # Delay before retrying could be adjusted based on specific needs
