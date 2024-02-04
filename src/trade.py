from utility import load_dotenv, read_csv, datetime, Avanza, OrderType, timedelta, initialize_avanza, getenv
import asyncio

load_dotenv()

# Avanza credentials
avanza = initialize_avanza()

file_path = r"./output/trades.csv"

# Track the last row processed
last_row_processed = 0

async def trade(avanza):
    global last_row_processed

    while True:
        try:
            trades = read_csv(file_path)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            continue

        current_datetime = datetime.now()  # Get the current datetime

        for index, row in trades.iloc[last_row_processed:].iterrows():
            try:
                trade_datetime = datetime.strptime(row['Date'], '%Y-%m-%d %H:%M:%S')

                # Skip the trade if the datetime is more than 5 seconds in the past
                if trade_datetime < (current_datetime - timedelta(seconds=120)):
                    print(f"Skipping past trade for {row['Ticker']} on {row['Date']}")
                    last_row_processed = index + 1
                    continue

                order_type = OrderType.BUY if row['Transaction Type'] == 'BUY' else OrderType.SELL
                order_book_id = row['Orderbook ID']
                volume = row['Shares']
                price = row['Price']
                valid_until = trade_datetime.date()  # Extract just the date part for valid_until

                result = avanza.place_order(
                    account_id=getenv('AVANZA_ACCOUNT_ID'),
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