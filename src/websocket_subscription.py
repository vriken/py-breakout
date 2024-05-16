# websocket_subscription.py
from asyncio import sleep as async_sleep
from websockets.exceptions import ConnectionClosedError
import backoff
from avanza import ChannelType

class WebSocketSubscription:
    def __init__(self, avanza, whitelisted_tickers, callback):
        self.avanza = avanza
        self.whitelisted_tickers = whitelisted_tickers
        self.callback = callback

    @backoff.on_exception(backoff.expo, ConnectionClosedError, max_tries=8)
    async def resilient_subscribe(self):
        await self.subscribe_to_channel()

    async def subscribe_to_channel(self):
        for _, id in self.whitelisted_tickers.items():
            while True:
                try:
                    await self.avanza.subscribe_to_id(ChannelType.QUOTES, str(id), self.callback)
                    break  # Break the loop if subscription is successful
                except ConnectionClosedError as e:
                    print(f"WebSocket connection closed unexpectedly: {e}. Reconnecting...")
                    await async_sleep(5)  # wait before reconnecting
                except Exception as e:
                    print(f"Error subscribing to channel: {e}")
                    break  # Exit loop on other exceptions, if appropriate

# Example usage:
# websocket_subscription = WebSocketSubscription(avanza, whitelisted_tickers, callback)
# asyncio.run(websocket_subscription.resilient_subscribe())
