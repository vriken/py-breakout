from utility import *

def implement_strategy(stock, investment, lower_length=None, upper_length=None):
    actions = []
    in_position = False
    equity = investment
    no_of_shares = 0

    # Remove 'date' column processing from here
    # Instead, use the index as the date

    for i in range(3, len(stock)):
        current_entry = stock['date'].iloc[i]

        if isinstance(current_entry, pd.Timestamp):
            # This is a datetime object, can be used directly or formatted
            current_date_or_datetime = current_entry.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # This is likely a date object or another format, use as is or convert/format accordingly
            current_date_or_datetime = str(current_entry)

        # Buy
        if stock['high'].iloc[i] >= stock['dcu'].iloc[i] and not in_position:
            no_of_shares = equity // stock.close.iloc[i]
            equity -= no_of_shares * stock.close.iloc[i]
            in_position = True
            actions.append({'Date': current_date_or_datetime, 'Action': 'BUY', 'Shares': no_of_shares, 'Price': stock.close.iloc[i], 'Volume': stock.volume.iloc[i]})
            fee = calculate_brokerage_fee(no_of_shares * stock.close.iloc[i])
            equity -= fee  # Deducting the transaction fee

        # Sell
        elif stock['low'].iloc[i] <= stock['dcl'].iloc[i] and in_position:
            equity += no_of_shares * stock.close.iloc[i]
            in_position = False
            actions.append({'Date': current_date_or_datetime, 'Action': 'SELL', 'Shares': no_of_shares, 'Price': stock.close.iloc[i], 'Volume': stock.volume.iloc[i]})
            fee = calculate_brokerage_fee(no_of_shares * stock.close.iloc[i])
            equity -= fee  # Deducting the transaction fee

    # Close
    if in_position:
        equity += no_of_shares * stock['close'].iloc[-1]
        in_position = False
        fee = calculate_brokerage_fee(no_of_shares * stock['close'].iloc[-1])
        equity -= fee  # Deducting the transaction fee

    earning = round(equity - investment, 2)

    return actions, equity, earning