from utility import datetime, OrderType, timedelta, getenv, initialize_avanza
import asyncio
import redis.asyncio as aioredis
from dotenv import load_dotenv

async def trade():
    load_dotenv()
    r = aioredis.Redis(host='localhost', port=6379, db=0)
    pubsub = r.pubsub()
    await pubsub.psubscribe('__keyspace@0__:*')  # Subscribe to all key events in database 0

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
            print(message)
            if message:
                key = message['channel'].split(':')[-1]  # Get the key from the channel name
                transaction_data = await r.hgetall(key)
                if b'shares' not in transaction_data or b'price' not in transaction_data:
                    continue

                order_book_id = key.decode('utf-8')
                shares = int(transaction_data[b'shares'])
                price = float(transaction_data[b'price'])
                transaction_type = transaction_data[b'type'].decode('utf-8') if b'type' in transaction_data else 'BUY'
                transaction_date = transaction_data[b'date'].decode('utf-8') if b'date' in transaction_data else datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                trade_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')
                current_datetime = datetime.now()
                if trade_datetime < (current_datetime - timedelta(seconds=20)):
                    continue

                order_type = OrderType.BUY if transaction_type == 'BUY' else OrderType.SELL
                valid_until = trade_datetime.date()
                print(order_type)

                try:
                    print(
                        account_id=getenv('AVANZA_ACCOUNT_ID'), 
                        order_book_id=order_book_id, 
                        order_type=order_type, 
                        price=price, 
                        valid_until=valid_until, 
                        volume=shares)
                except Exception as e:
                    print(f"Error placing order: {e}")

    finally:
        await pubsub.close()
        await r.aclose()
        print("Redis connections closed.")

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(trade())
    finally:
        loop.close()

if __name__ == '__main__':
    # avanza = initialize_avanza()
    main()
