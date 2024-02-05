from utility import initialize_avanza, read_csv, datetime, ChannelType
import asyncio

#avanza = initialize_avanza()

#stocks = read_csv('./input/best_tickers.csv')
stocks = read_csv('/Users/ake/Documents/probable_spoon_a/input/best_tickers.csv')
whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))

current_date = datetime.now().strftime("%Y-%m-%d")

def callback(data):
    orderbook_id = data['data']['orderbookId']
    buy_price = data['data']['buyPrice']
    sell_price = data['data']['sellPrice']
    updated_timestamp = data['data']['updated']
    
    updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0)
    
    with open(f"/Users/ake/Documents/probable_spoon_a/input/realtime_data_{current_date}_data.csv", 'a') as file:
        file.write(f"{orderbook_id}, {buy_price}, {sell_price}, {updated_datetime}\n")


async def subscribe_to_channel(avanza, whitelisted_tickers):
    for ticker, id in whitelisted_tickers.items():
        await avanza.subscribe_to_id(
            ChannelType.QUOTES,
            str(id),
            callback
        )

def main():
    #avanza = None
    while True:
        try:
            avanza = initialize_avanza()
            #stocks = read_csv('./input/best_tickers.csv')
            stocks = read_csv('/Users/ake/Documents/probable_spoon_a/input/best_tickers.csv')
            whitelisted_tickers = dict(zip(stocks['ticker'], stocks['id']))

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(subscribe_to_channel(avanza, whitelisted_tickers))
            loop.run_forever()
        except Exception as e:
            print(f"Error occurred: {e}. Restarting initialization...")
            # Optionally, add a sleep here if you want to wait before retrying
            # time.sleep(10)

if __name__ == "__main__":
    main()
