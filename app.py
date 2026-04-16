from flask import Flask, render_template, redirect, url_for, session, request

app = Flask(__name__)

app.secret_key = 'ditec_secret_key_bb'

USUARIOS = {
    "igor.barbosa": {"senha": "123", "nome": "Igor Barbosa", "nivel": "Gestão"},
    "visitante": {"senha": "abc", "nome": "Usuário Visitante", "nivel": "Consulta"}
}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario_input = request.form.get('username')
        senha_input = request.form.get('password')

        user = USUARIOS.get(usuario_input)

        if user and user['senha'] == senha_input:
            session['user_name'] = user['nome']
            session['user_level'] = user['nivel']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', erro=True)
    
    return render_template('login.html')

@app.route('/')
def index():
    if 'user_name' not in session:
        return redirect(url_for('login'))
        
    return render_template('index.html', 
                           user_level=session.get('user_level'), 
                           user_name=session.get('user_name'),
                           page_title="Página Inicial")

@app.route('/agencias')
def agencias():
    if 'user_name' not in session:
        return redirect(url_for('login'))
        
    return render_template('agencias.html', 
                           user_level=session.get('user_level'), 
                           user_name=session.get('user_name'),
                           page_title="Consulta Nacional de Agências")

@app.route('/detalhes/<prefixo>')
def detalhes(prefixo):
    if 'user_name' not in session:
        return redirect(url_for('login'))
    
    agencia_exemplo = {
        "prefixo": prefixo,
        "nome": "Recife Antigo",
        "cidade": "Recife",
        "estado": "PE",
        "endereco": "Cais do Apolo, 123 - Bairro do Recife"
    }
        
    return render_template('detalhes.html', 
                           user_level=session.get('user_level'), 
                           user_name=session.get('user_name'),
                           page_title=f"Agência {prefixo} - Engenharia",
                           agencia=agencia_exemplo)

@app.route('/mapa')
def mapa():
    if 'user_name' not in session:
        return redirect(url_for('login'))
        
    return render_template('mapa.html', 
                           user_level=session.get('user_level'), 
                           user_name=session.get('user_name'),
                           page_title="Localizador de Agências")

@app.route('/dashboard')
def dashboard():
    if 'user_name' not in session:
        return redirect(url_for('login'))

    stats_dashboard = {
        'em_reforma': 15,
        'consumo_energia': '1.240 kWh',
        'consumo_agua': '42 m³',
        'carbono_status': '94%'
    }
        
    return render_template('dashboard.html', 
                           user_level=session.get('user_level'), 
                           user_name=session.get('user_name'),
                           page_title="Dashboard Estratégico DITEC",
                           stats=stats_dashboard)

@app.route('/admin')
def admin():
    stats = {
        'em_reforma': 15,
        'consumo_energia': 1240,
        'consumo_agua': 42,
        'carbono': 94
    }

    return render_template('admin.html', 
                           stats=stats, 
                           user_name="Igor Barbosa", 
                           user_level="Gestão", 
                           page_title="Gestão DITEC")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
