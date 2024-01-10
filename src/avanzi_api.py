from utility import load_dotenv, os, pd, time, datetime, ChannelType, Avanza, asyncio

load_dotenv()

start_time = time(8, 58)
end_time = time(17, 2)
request_delay_seconds = 60  # Adjust the delay as needed

whitelisted_tickers = {'TRANS.ST' :  564938, 'SYSR.ST' : 97407, 'SANION.ST' : 475457, 'CNCJO.ST' : 5279, 'INDT.ST' : 26607,
                        'INSTAL.ST' : 752039, 'KDEV.ST' : 285632, 'K2A-B.ST' : 971402, 'NETI-B.ST' : 5440, 'NIBE-B.ST' : 5325}
best_tickers = pd.read_csv('/workspaces/probable_spoon/input/best_whitelisted.csv')
best_tickers = best_tickers[best_tickers['ticker'].isin(whitelisted_tickers.keys())]

# print(whitelisted_tickers.head())

def callback(data):
    # Use 'data' directly since it is already a dictionary
    orderbook_id = data['data']['orderbookId']
    buy_price = data['data']['buyPrice']
    sell_price = data['data']['sellPrice']
    updated_timestamp = data['data']['updated']

    # Convert timestamp from milliseconds to datetime
    updated_datetime = datetime.fromtimestamp(updated_timestamp / 1000.0)

    # Save data to a file (you could also save to a database)
    with open('input/realtime_data.txt', 'a') as file:
        file.write(f"{orderbook_id}, {buy_price}, {sell_price}, {updated_datetime}\n")


async def subscribe_to_channel(avanza: Avanza):
    for ticker, id in whitelisted_tickers.items():
        await avanza.subscribe_to_id(
            ChannelType.QUOTES,
            str(id),
            callback
        )


def main():
    avanza = Avanza({
        'username': os.getenv('AVANZA_USERNAME'),
        'password': os.getenv('AVANZA_PASSWORD'),
        'totpSecret': os.getenv('AVANZA_TOTP_SECRET')
    })

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(subscribe_to_channel(avanza))
    loop.run_forever()

if __name__ == "__main__":
    main()
