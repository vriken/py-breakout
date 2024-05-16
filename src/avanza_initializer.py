import os
import time
from dotenv import load_dotenv
from avanza import Avanza

class AvanzaInitializer:
    @staticmethod
    def initialize_avanza():
        load_dotenv()
        while True:
            try:
                avanza = Avanza({
                    'username': os.getenv('AVANZA_USERNAME'),
                    'password': os.getenv('AVANZA_PASSWORD'),
                    'totpSecret': os.getenv('AVANZA_TOTP_SECRET')
                })
                return avanza
            except Exception as e:
                if "500" in str(e):
                    print("Received a 500 error. Retrying in 30 seconds...\n")
                    time.sleep(60)
                else:
                    print(f"Failed to authenticate: {e}")
                    time.sleep(10)
                    raise e

# Example usage:
# avanza = AvanzaInitializer.initialize_avanza()
