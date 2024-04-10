from utility import initialize_avanza, read_csv, datetime, ChannelType, sleep
import asyncio
import backoff
import websockets

avanza = None

# Callback function to process data received from the subscription
def callback(data):
    current_date = datetime.now().strftime("%Y-%m-%d")

    orderbook_id = data['data']['orderbookId']
    buy_price = data['data']['buyPrice']
    sell_price = data['data']['sellPrice']
    updated_timestamp = data['data']['updated']
    
    updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0)
    
    with open(f"/Users/ake/Documents/probable_spoon_a/input/realtime_data_{current_date}_data.csv", 'a') as file:
        file.write(f"{orderbook_id}, {buy_price}, {sell_price}, {updated_datetime}\n")

# Define a backoff strategy for subscribing to channels
@backoff.on_exception(backoff.expo,
                      (asyncio.TimeoutError, websockets.exceptions.ConnectionClosedError),
                      max_tries=8)
async def resilient_subscribe(avanza, whitelisted_tickers):
    await subscribe_to_channel(avanza, whitelisted_tickers)

# Function to subscribe to channels based on the whitelisted tickers
async def subscribe_to_channel(avanza, whitelisted_tickers):
    for ticker, id in whitelisted_tickers.items():
        try:
            await avanza.subscribe_to_id(
                ChannelType.QUOTES,
                str(id),
                callback
            )
            print(f"Subscribed to {ticker} successfully.")
        except Exception as e:
            print(f"Failed to subscribe to {ticker}: {e}")

def main():
    global avanza  # Use the global declaration to modify the global instance
    while True:
        try:
            if avanza is None:  # Initialize avanza only if it's not already initialized
                avanza = initialize_avanza()
            
            stocks = read_csv('/Users/ake/Documents/probable_spoon_a/input/best_tickers.csv')
            whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(resilient_subscribe(avanza, whitelisted_tickers))
            loop.run_forever()
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"WebSocket connection closed: {e}. Attempting to reconnect...")
            avanza = None  # Reset avanza so it can be reinitialized in the next iteration
            sleep(10)  # Consider implementing a more sophisticated backoff here
        except Exception as e:
            print(f"Error occurred: {e}. Restarting initialization...")
            avanza = None  # Reset avanza on other exceptions as well
            sleep(10)

if __name__ == "__main__":
    main()
