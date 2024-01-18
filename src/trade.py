from utility import load_dotenv, os, pd, datetime, Avanza, OrderType, asyncio

load_dotenv()

# Avanza credentials
avanza = Avanza({
    'username': os.getenv('AVANZA_USERNAME'),
    'password': os.getenv('AVANZA_PASSWORD'),
    'totpSecret': os.getenv('AVANZA_TOTP_SECRET')
})

file_path = r"./output/trades.csv"

# Track the last row processed
last_row_processed = 0

async def trade(avanza):
    global last_row_processed

    while True:
        try:
            trades = pd.read_csv(file_path)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            continue

        current_date = datetime.now().date()  # Get the current date

        for index, row in trades.iloc[last_row_processed:].iterrows():
            try:
                date_str = row['Date'].split(' ')[0]
                trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()

                # Skip the trade if the date is in the past
                if trade_date < current_date:
                    print(f"Skipping past trade for {row['Ticker']} on {date_str}")
                    last_row_processed = index + 1
                    continue

                order_type = OrderType.BUY if row['Transaction Type'] == 'BUY' else OrderType.SELL
                order_book_id = row['Orderbook ID']
                volume = row['Shares']
                price = row['Price']
                valid_until = trade_date

                result = avanza.place_order(
                    account_id=os.getenv('AVANZA_ACCOUNT_ID'),
                    order_book_id=order_book_id,
                    order_type=order_type,
                    price=price,
                    valid_until=valid_until,
                    volume=volume
                )
                print(result)
                last_row_processed = index + 1
            except Exception as e:
                print(f"Error processing row {index}: {e}")
        

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(trade(avanza))

if __name__ == '__main__':
    main()
