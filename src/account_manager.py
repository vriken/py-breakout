import os

class AccountManager:
    def __init__(self, avanza):
        self.avanza = avanza

    def get_balance(self):
        try:
            data = self.avanza.get_overview()
            balance = next((account['balance']['value'] for account in data['accounts'] if account['id'] == os.getenv('AVANZA_ACCOUNT_ID')), 0)
            return balance
        except KeyError as e:
            print(f"Error accessing balance data: {e}. The API response structure might have changed.")
        except Exception as e:
            print(f"Unexpected error fetching balance: {e}")
        return 0

    def get_owned_stocks(self, owned_stocks_dict=None):
        if owned_stocks_dict is None:
            owned_stocks_dict = {}
        try:
            data = self.avanza.get_accounts_positions()
            if 'withOrderbook' not in data:
                print("No 'withOrderbook' key found in the data dictionary.")
                return owned_stocks_dict

            for entry in data['withOrderbook']:
                try:
                    account = entry['account']
                    if account['id'] != os.getenv('AVANZA_ACCOUNT_ID'):
                        continue

                    instrument = entry['instrument']
                    volume = entry['volume']['value']
                    orderbook_id = instrument['orderbook']['id']
                    orderbook_name = instrument['name']

                    buy_price = instrument.get('orderbook', {}).get('quote', {}).get('buy', {}).get('value')

                    if buy_price is not None:
                        owned_stocks_dict[orderbook_id] = {
                            'name': orderbook_name,
                            'price': buy_price,
                            'shares': volume,
                            'id': orderbook_id
                        }
                except KeyError as e:
                    print(f"Error processing stock entry: {e}. Skipping this entry.")
                except Exception as e:
                    print(f"Unexpected error processing stock entry: {e}. Skipping this entry.")

            return owned_stocks_dict
        except KeyError as e:
            print(f"Error accessing account positions data: {e}. The API response structure might have changed.")
        except Exception as e:
            print(f"Unexpected error fetching owned stocks: {e}")
        return {}
