from utility import load_dotenv, os, pd, time, datetime, ChannelType, Avanza, asyncio

load_dotenv()
avanza = Avanza({
    'username': os.getenv('AVANZA_USERNAME'),
    'password': os.getenv('AVANZA_PASSWORD'),
    'totpSecret': os.getenv('AVANZA_TOTP_SECRET')
})

# Load the CSV file
selected_stocks_df = pd.read_csv('./input/best_tickers.csv')
# Convert the 'ticker' and 'id' columns to a dictionary
whitelisted_tickers = dict(zip(selected_stocks_df['ticker'], selected_stocks_df['id']))

current_date = datetime.now().strftime("%Y-%m-%d")

def callback(data):
    # Use 'data' directly since it is already a dictionary
    orderbook_id = data['data']['orderbookId']
    buy_price = data['data']['buyPrice']
    sell_price = data['data']['sellPrice']
    updated_timestamp = data['data']['updated']

    # Convert timestamp from milliseconds to datetime
    updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0)

    # Save data to a file (you could also save to a database)
    with open(f"./input/realtime_data_{current_date}_data.csv", 'a') as file:
        file.write(f"{orderbook_id}, {buy_price}, {sell_price}, {updated_datetime}\n")


async def subscribe_to_channel(avanza: Avanza):
    for ticker, id in whitelisted_tickers.items():
        await avanza.subscribe_to_id(
            ChannelType.QUOTES,
            str(id),
            callback
        )


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(subscribe_to_channel(avanza))
    loop.run_forever()

if __name__ == "__main__":
    main()
