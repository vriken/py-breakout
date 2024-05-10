from utility import datetime, OrderType, timedelta, getenv
import asyncio
import redis.asyncio as aioredis
from dotenv import load_dotenv


async def trade(avanza):
    load_dotenv()
    # Connect to Redis using the async Redis client
    r = aioredis.Redis(host='localhost', port=6379, db=0)
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    key_name = f"transactions:{current_date}"  # Assume transaction logs are stored daily

    last_processed_index = 0  # Track the last processed index

    while True:
        try:
            # Fetch all transactions from Redis for the current day
            transactions = await r.lrange(key_name, 0, -1)
            for index, transaction_str in enumerate(transactions[last_processed_index:], start=last_processed_index):
                transaction_data = transaction_str.split(',')
                transaction_type, ticker, order_book_id, shares, price, transaction_date, _ = transaction_data

                trade_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')
                current_datetime = datetime.now()  # Get the current datetime

                if trade_datetime < (current_datetime - timedelta(seconds=120)):
                    continue

                order_type = OrderType.BUY if transaction_type == 'BUY' else OrderType.SELL
                volume = int(shares)
                price = float(price)
                valid_until = trade_datetime.date()

                try:
                    result = await avanza.place_order(
                        account_id=getenv('AVANZA_ACCOUNT_ID'),
                        order_book_id=order_book_id,
                        order_type=order_type,
                        price=price,
                        valid_until=valid_until,
                        volume=volume
                    )

                    print(result)
                except Exception as e:
                    print(f"Error placing order: {e}")

                last_processed_index = index + 1  # Update the last processed index

            # Sleep before the next iteration to avoid too frequent polling
            await asyncio.sleep(60)  # 60 seconds wait time

        except Exception as e:
            print(f"Error reading transactions from Redis: {e}")

def main(avanza):
    """Sets up the asyncio loop for the trade coroutine."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(trade(avanza))
    loop.close()

if __name__ == '__main__':
    print("This script should be run from the main script to ensure proper handling of the Avanza object.")