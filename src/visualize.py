import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def visualize_stock(stock, actions):
    # Ensure the 'date' column is datetime
    if not pd.api.types.is_datetime64_any_dtype(stock['date']):
        stock['date'] = pd.to_datetime(stock['date'])
    stock.set_index('date', inplace=True)
    
    plt.figure(figsize=(10, 6))
    
    # Plotting the stock data
    plt.plot(stock.index, stock['close'], label='CLOSE', alpha=0.5)
    plt.plot(stock.index, stock['dcl'], color='black', linestyle='--', alpha=0.3)
    plt.plot(stock.index, stock['dcm'], color='orange', label='DCM', alpha=0.5)
    plt.plot(stock.index, stock['dcu'], color='black', linestyle='--', alpha=0.3, label='DCU,DCL')
    
    # Initialize the last buy price
    last_buy_price = None
    last_buy_date = None
    
    # Plotting actions
    for action in actions:
        action_date = pd.to_datetime(action['Date'])
        price = action['Price']
        action_type = action['Action']
        
        # Set the color for the scatter plot based on action type
        action_color = 'green' if action_type == 'BUY' else 'red'
        plt.scatter(action_date, price, color=action_color, label=f'{action_type} at {price} SEK', alpha=0.5)
        
        # If it's a buy action, remember the price and date
        if action_type == 'BUY':
            last_buy_price = price
            last_buy_date = action_date
        # If it's a sell action, draw a line from the last buy action
        elif action_type == 'SELL' and last_buy_price is not None:
            line_color = 'green' if price > last_buy_price else 'red'
            plt.plot([last_buy_date, action_date], [last_buy_price, price], color=line_color, linestyle='--', alpha=0.7, linewidth=2)
            # Reset the last buy price after a sell
            last_buy_price = None
    
    # Format the date axis
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gcf().autofmt_xdate()  # Beautify the date labels
    plt.xlabel('Date')
    plt.ylabel('Price (SEK)')
    plt.title('Stock Price with Buy/Sell Transactions')
    plt.grid(True)
    
    # Remove duplicate labels
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    # plt.legend(by_label.values(), by_label.keys())
    
    return plt
