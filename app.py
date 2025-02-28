from flask import Flask
from complaint_bot import complaint_bot
from sample_chat import sample_chat
from sample import sample
from login import login
from certificate import certificate
from fetch import fetch
from certi_gen import certi_gen

app = Flask(__name__)

app.register_blueprint(complaint_bot, url_prefix='/complaint_bot')
app.register_blueprint(sample_chat, url_prefix='/sample_chat')
app.register_blueprint(sample, url_prefix='/sample')
app.register_blueprint(login, url_prefix='/login')
app.register_blueprint(certificate, url_prefix='/certificate')
app.register_blueprint(fetch, url_prefix='/fetch')
app.register_blueprint(certi_gen, url_prefix='/certi_gen')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500, debug=True)


