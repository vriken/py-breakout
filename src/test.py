import redis
from datetime import datetime
transaction_type = 'BUY'
redis_client = redis.Redis(host='localhost', port=6379, db=0)
transaction_data = {
    'type': transaction_type,
    # 'ticker': ticker, # needs fixing
    'shares': '50',
    'price': 1,
    'date': str(datetime.now())
}
list_key = f"transactions:BUY"
redis_client.hset('12352164', mapping=transaction_data)

# import redis
# from datetime import datetime
# transaction_type = 'BUY'
# redis_client = redis.Redis(host='localhost', port=6379, db=0)
# transaction_data = {
#     'buyPrice': 400,
#     'sellPrice': 399,
#     'updated': '2024-05-10 19:37:50'
# }
# list_key = f"transactions:BUY"
# redis_client.hset('1235164', mapping=transaction_data)

