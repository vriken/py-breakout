from utility import datetime, OrderType, timedelta, getenv, initialize_avanza
import asyncio
import redis.asyncio as aioredis
from dotenv import load_dotenv

async def trade(avanza):
    load_dotenv()
    r = aioredis.Redis(host='localhost', port=6379, db=0)

    try:
        while True:
            # Fetch all keys that end with 'BUY'
            buy_keys = await r.keys('*BUY')
            # Fetch all keys that end with 'SELL'
            sell_keys = await r.keys('*SELL')

            # Combine the lists of keys
            keys = list(set(buy_keys + sell_keys))  # Remove duplicates by converting to a set and back to a list

            for key in keys:
                transaction_data = await r.hgetall(key)
                if b'orderbook_id' not in transaction_data or b'shares' not in transaction_data or b'price' not in transaction_data:
                    print(f"Missing data for key: {key.decode()}")
                    continue

                order_book_id = transaction_data[b'orderbook_id'].decode('utf-8')
                shares = int(transaction_data[b'shares'])
                price = float(transaction_data[b'price'])
                transaction_type = transaction_data[b'type'].decode('utf-8') if b'type' in transaction_data else 'BUY' # Default to BUY if missing
                transaction_date = transaction_data[b'date'].decode('utf-8') if b'date' in transaction_data else datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                trade_datetime = datetime.strptime(transaction_date, '%Y-%m-%d %H:%M:%S')
                current_datetime = datetime.now()

                if trade_datetime < (current_datetime - timedelta(seconds=120)):
                    continue  # Skip old transactions

                order_type = OrderType.BUY if transaction_type == 'BUY' else OrderType.SELL
                valid_until = trade_datetime.date()

                try:
                    result = avanza.place_order(
                        account_id=getenv('AVANZA_ACCOUNT_ID'),
                        order_book_id=order_book_id,
                        order_type=order_type,
                        price=price,
                        valid_until=valid_until,
                        volume=shares
                    )
                    print(result)
                except Exception as e:
                    print(f"Error placing order: {e}")

    finally:
        await r.aclose()
        print("Redis connection closed.")        
def main():
    avanza = initialize_avanza()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(trade(avanza))
    finally:
        loop.close()

if __name__ == '__main__':
    main()