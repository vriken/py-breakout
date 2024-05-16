import os
from avanza_initializer import AvanzaInitializer

class AccountManager:
    def __init__(self, avanza):
        self.avanza = avanza

    def get_balance(self):
        try:
            data = self.avanza.get_overview()
        except:
            self.avanza = AvanzaInitializer.initialize_avanza()
            data = self.avanza.get_overview()

        budget = 0
        for account in data['accounts']:
            if account['id'] == os.getenv('AVANZA_ACCOUNT_ID'):
                budget = account['balance']['value']
                break

        return budget

    def get_owned_stocks(self, owned_stocks_dict):
        try:
            data = self.avanza.get_accounts_positions()
        except:
            self.avanza = AvanzaInitializer.initialize_avanza()
            data = self.avanza.get_accounts_positions()

        if 'withOrderbook' in data:
            for entry in data['withOrderbook']:
                account = entry['account']
                if account['id'] == os.getenv('AVANZA_ACCOUNT_ID'):
                    instrument = entry['instrument']
                    volume = entry['volume']['value']
                    orderbook_id = instrument['orderbook']['id']
                    orderbook_name = instrument['name']

                    if 'orderbook' in instrument and 'quote' in instrument['orderbook'] and instrument['orderbook']['quote']['buy'] is not None:
                        buy_price = instrument['orderbook']['quote']['buy']['value']
                        owned_stocks_dict[orderbook_id] = {'name': orderbook_name, 'price': buy_price, 'shares': volume, 'id': orderbook_id}
                    else:
                        break
        else:
            print("No 'withOrderbook' key found in the data dictionary.")

        return owned_stocks_dict

# Example usage:
# account_manager = AccountManager(avanza)
# balance = account_manager.get_balance()
# owned_stocks = account_manager.get_owned
