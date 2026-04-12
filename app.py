from flask import Flask, render_template, redirect, url_for, session, request

app = Flask(__name__)
# Chave secreta para manter a sessão segura
app.secret_key = 'ditec_secret_key_bb'

# Base de dados em memória para autenticação
# Certifique-se de que a string 'Gestão' no seu index.html seja idêntica a esta (com acento e G maiúsculo)
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
        
        # Validação de credenciais
        if user and user['senha'] == senha_input:
            session['user_name'] = user['nome']
            session['user_level'] = user['nivel']
            return redirect(url_for('index'))
        else:
            # Retorna erro=True para exibir o aviso visual no login.html
            return render_template('login.html', erro=True)
    
    return render_template('login.html')

@app.route('/')
def index():
    # Proteção de rota: redireciona se não houver sessão ativa
    if 'user_name' not in session:
        return redirect(url_for('login'))
        
    return render_template('index.html', 
                           user_level=session.get('user_level'), 
                           user_name=session.get('user_name'),
                           page_title="Página Inicial")

@app.route('/mapa')
def mapa():
    # Proteção de rota para o mapa
    if 'user_name' not in session:
        return redirect(url_for('login'))
        
    return render_template('mapa.html', 
                           user_level=session.get('user_level'), 
                           user_name=session.get('user_name'),
                           page_title="Localizador de Agências")

@app.route('/logout')
def logout():
    # Limpa todos os dados da sessão (nome e nível)
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    # Rodando em modo debug para facilitar o desenvolvimento no VS Code
    app.run(debug=True)