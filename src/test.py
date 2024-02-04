from utility import load_dotenv, Avanza, os



load_dotenv()
avanza = Avanza({
    'username': os.getenv('AVANZA_USERNAME'),
    'password': os.getenv('AVANZA_PASSWORD'),
    'totpSecret': os.getenv('AVANZA_TOTP_SECRET')
})


avanza.get_overview()

