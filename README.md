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
