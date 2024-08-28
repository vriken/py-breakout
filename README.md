# How to use
 1. Create .env file containing your avanza username, password totp secret and account id in the following format
 ```
    AVANZA_USERNAME="yourusername"
    AVANZA_PASSWORD="yourpassword"
    AVANZA_TOTP_SECRET="yourtotpsecret"
    AVANZA_ACCOUNT_ID="youraccountid"
 ```
 3. run ```docker-compose up --build```
 4. If you already built, just run docker-compose up


OR, create the .env and run the main.py in /src/


# TODO
│   1 Error Handling and Logging:                                              │
│      • Implement a more robust logging system throughout the project. This   │
│        will help with debugging and monitoring the system's performance.     │
│      • Enhance error handling in the WebSocketSubscription class,            │
│        particularly around reconnection logic.                               │
│   2 Configuration Management:                                                │
│      • Move hardcoded values (like the brokerage fee percentage in           │
│        TradingLogic) to a configuration file. This will make it easier to    │
│        adjust parameters without changing the code.                          │
│   3 Performance Optimization:                                                │
│      • Consider using async operations more extensively, especially in the   │
│        AccountManager and DataManager classes.                               │
│      • Optimize the historical data fetching process in main.py to reduce    │
│        startup time.                                                         │
│   4 Code Structure and Modularity:                                           │
│      • Split the TradingLogic class into smaller, more focused classes       │
│        (e.g., separate classes for Donchian channel calculation and order    │
│        execution).                                                           │
│      • Implement a Strategy pattern to allow for easy switching between      │
│        different trading strategies.                                         │
│   5 Data Management:                                                         │
│      • Implement a more efficient data storage solution for historical data, │
│        possibly using a lightweight database like SQLite.                    │
│      • Add data validation and sanitization to ensure the integrity of       │
│        incoming data.                                                        │
│   6 Testing:                                                                 │
│      • Implement unit tests for critical components, especially the trading  │
│        logic and data processing functions.                                  │
│      • Add integration tests to ensure different parts of the system work    │
│        well together.                                                        │
│   7 Risk Management:                                                         │
│      • Implement additional risk management features, such as stop-loss      │
│        orders and position sizing based on account equity.                   │
│      • Add a daily loss limit to prevent excessive losses.                   │
│   8 Performance Monitoring:                                                  │
│      • Implement a system to track and report on the performance of your     │
│        trading strategy.                                                     │
│      • Add functionality to generate regular reports on trades,              │
│        profits/losses, and other key metrics.                                │
│   9 Security Enhancements:                                                   │
│      • Review and enhance the security of the authentication process in      │
│        AvanzaInitializer.                                                    │
│      • Implement proper encryption for sensitive data, especially in         │
│        environment variables.                                                │
│  10 User Interface:                                                          │
│      • Consider adding a simple web interface for monitoring the system's    │
│        status and performance in real-time.                                  │
│  11 Backtesting Capability:                                                  │
│      • Implement a backtesting module to test your trading strategy on       │
│        historical data before running it live.                               │
│  12 Code Documentation:                                                      │
│      • Enhance inline comments and add docstrings to improve code            │
│        readability and maintainability.                                      │
│  13 Dependency Management:                                                   │
│      • Use a requirements.txt file or a more advanced tool like Poetry to    │
│        manage project dependencies.                                          │
│  14 Continuous Integration/Continuous Deployment (CI/CD):                    │
│      • Set up a CI/CD pipeline for automated testing and deployment.         │
