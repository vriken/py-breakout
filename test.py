from pyotp import TOTP
from hashlib import sha1
from avanza import Avanza, TimePeriod
from os import getenv
from dotenv import load_dotenv

load_dotenv()

# Avanza credentials
avanza = Avanza({
    'username': getenv('AVANZA_USERNAME')
    ,'password': getenv('AVANZA_PASSWORD')
    ,'totpSecret': getenv('AVANZA_TOTP_SECRET')
})

report = avanza.get_insights_report(
    account_id= getenv('AVANZA_ACCOUNT_ID'),
    time_period=TimePeriod.ONE_WEEK
)

print(report)