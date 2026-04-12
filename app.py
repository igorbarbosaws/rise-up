from flask import Flask, render_template

app = Flask(__name__)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/')
def index():
    return render_template('index.html', user_level='admin', user_name='Igor Barbosa')

@app.route('/mapa')
def mapa():
    return render_template('mapa.html', user_level='admin')

if __name__ == '__main__':
    app.run(debug=True)