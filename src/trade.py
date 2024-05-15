from utility import datetime, OrderType, timedelta, getenv, read_parquet, initialize_avanza
import asyncio
from dotenv import load_dotenv
import os
load_dotenv()

base_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
file_path = f"{base_path}/output/trades.parquet"

# Track the last row processed
last_row_processed = 0

# def send_email(subject, body):
#     msg = MIMEText(body)
#     msg['Subject'] = subject
#     msg['From'] = getenv('EMAIL_SENDER')
#     msg['To'] = getenv('EMAIL_RECEIVER')
#     with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
#         smtp.login(getenv('EMAIL_SENDER'), getenv('EMAIL_PASSWORD'))
#         smtp.sendmail(getenv('EMAIL_SENDER'), getenv('EMAIL_RECEIVER'), msg.as_string())

async def trade(avanza):
    global last_row_processed
    while True:
        try:
            trades = read_parquet(file_path)
        except Exception as e:
            print(f"Error reading Parquet file: {e}")
            await asyncio.sleep(30)  # Wait before retrying to avoid rapid retries on failure
            continue

        current_datetime = datetime.now()  # Get the current datetime

        for index, row in trades.iloc[last_row_processed:].iterrows():
            trade_datetime = row['transaction_date']
            if isinstance(trade_datetime, str):
                trade_datetime = datetime.strptime(trade_datetime, '%Y-%m-%d %H:%M:%S')
            if trade_datetime < (current_datetime - timedelta(seconds=60)):
                # print(f"Skipping past trade for {row['Ticker']} on {row['Date']}")
                last_row_processed = index + 1
                continue

            order_type = OrderType.BUY if row['transaction_type'] == 'BUY' else OrderType.SELL
            order_book_id = row['orderbook_id']
            volume = row['shares']
            price = row['price']
            valid_until = trade_datetime.date()

            try:
                result = avanza.place_order(
                    account_id=getenv('AVANZA_ACCOUNT_ID'),
                    order_book_id=order_book_id,
                    order_type=order_type,
                    price=price,
                    valid_until=valid_until,
                    volume=volume
                )
                # email_body = f"Trade Executed: {result}"
                # send_email("Trade Notification", email_body)
                print(result)
                last_row_processed = index + 1
            except Exception as e:
                print(f"Error processing row {index}: {e}")

def main(avanza):
    """Sets up the asyncio loop for the trade coroutine."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(trade(avanza))
    loop.close()

if __name__ == '__main__':
    avanza = initialize_avanza()
    main(avanza)
    # print("This script should be run from the main script to ensure proper handling of the Avanza object.")
