from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Halo, Web App Python Berhasil Jalan!"

if __name__ == '__main__':
    app.run()