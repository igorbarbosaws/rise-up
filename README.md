# DISEC — Sistema de Gestão de Infraestrutura de Agências

> Desenvolvido durante a residência tecnológica do Porto Digital, este sistema web visa otimizar a gestão e o monitoramento de agências bancárias através de análises estratégicas avançadas.

---

## Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Demo](#demo)
- [Funcionalidades](#funcionalidades)
- [Tecnologias](#tecnologias)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Como Executar](#como-executar)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Níveis de Acesso](#níveis-de-acesso)
- [API REST](#api-rest)
- [Licença](#licença)

---

## Sobre o Projeto

O **DISEC** é uma aplicação web desenvolvida para centralizar o gerenciamento de informações de agências bancárias. O sistema permite acompanhar dados operacionais, indicadores de sustentabilidade, conformidade com vistorias do Corpo de Bombeiros, arquivos técnicos (DWG), horários de atendimento (SAA) e muito mais, tudo em um painel estratégico com visualização por mapa.

---

## Demo

A aplicação está disponível online via PythonAnywhere:

🔗 **[https://riseup.pythonanywhere.com](https://riseup.pythonanywhere.com)**

Use as credenciais abaixo para explorar o sistema:

| Usuário | Senha | Nível |
|---|---|---|
| `visitante` | `abc` | Consulta |

---

## Funcionalidades

- **Dashboard estratégico** com indicadores agregados de toda a rede de agências
- **Consulta nacional** de agências com filtros por nome, município, UF e classificação BACEN
- **Detalhamento por agência**: dados cadastrais, endereço, geolocalização e métricas
- **Indicador IDI** (Índice de Desempenho de Infraestrutura) com limiar configurável
- **Métricas de sustentabilidade**: consumo de energia, água, resíduos sólidos, eficiência energética e carbono
- **Gestão de vistorias do Corpo de Bombeiros**: protocolo, validade e upload de PDF
- **Upload e download de arquivos DWG** (plantas técnicas) por agência
- **Horários SAA** (Serviço de Atendimento ao Cliente) por dia da semana
- **Gestão de usuários** com controle de níveis de acesso
- **Mapa interativo** com marcadores coloridos por IDI (via Google Maps)
- **Classificação BACEN** das agências (Agência, PAB, PAE, UAB, Correspondente Bancário)

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3 + Flask 3.0 |
| ORM | Flask-SQLAlchemy 3.1 |
| Banco de dados | SQLite (desenvolvimento) / PostgreSQL (produção) |
| Autenticação | Werkzeug (hash de senhas) + Flask Session |
| Templates | Jinja2 3.1 |
| Frontend | HTML/CSS/JS + Google Maps API |
| Upload de arquivos | Werkzeug (DWG até 50 MB, PDF até 20 MB) |

---

## Estrutura do Projeto

```
disec/
├── app.py                  # Aplicação principal (models, rotas, API)
├── data/
│   └── agencias.json       # Dados iniciais das agências (seed)
├── uploads/
│   ├── dwg/                # Arquivos DWG por agência
│   └── bombeiros/          # PDFs de vistoria por agência
├── templates/
│   ├── login.html
│   ├── index.html
│   ├── agencias.html
│   ├── detalhes.html
│   ├── dashboard.html
│   ├── admin.html
│   └── errors/
│       ├── 403.html
│       ├── 404.html
│       └── 500.html
├── static/                 # CSS, JS, imagens
├── requirements.txt
└── README.md
```

---

## Como Executar

### Pré-requisitos

- Python 3.10 ou superior
- pip

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/disec.git
cd disec

# 2. Crie e ative um ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Execute a aplicação
python app.py
```

Acesse em: [http://localhost:5000](http://localhost:5000)

> O banco de dados SQLite (`disec.db`) e os usuários iniciais são criados automaticamente na primeira execução.

### Credenciais padrão

| Usuário | Senha | Nível |
|---|---|---|
| `visitante` | `abc` | Consulta |

> ⚠️ Altere as credenciais padrão antes de qualquer uso em ambiente externo.

---

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `SECRET_KEY` | Chave secreta da sessão Flask | `fallback_inseguro_troque_em_producao` |
| `DATABASE_URL` | URL de conexão com o banco | `sqlite:///disec.db` |
| `GOOGLE_MAPS_API_KEY` | Chave da API do Google Maps | _(vazio — mapa desabilitado)_ |
| `FLASK_DEBUG` | Ativa o modo debug | `False` |

Exemplo com PostgreSQL:

```bash
export DATABASE_URL="postgresql://usuario:senha@localhost/disec"
export SECRET_KEY="sua-chave-secreta-segura"
export GOOGLE_MAPS_API_KEY="sua-chave-google-maps"
python app.py
```

---

## Níveis de Acesso

| Nível | Permissões |
|---|---|
| **Consulta** | Visualizar agências, dashboard, detalhes e download de arquivos |
| **Gestão** | Tudo acima + criar/editar/excluir agências, usuários, vistorias, DWGs e configurações |

---

## API REST

Todas as rotas exigem autenticação via sessão. Rotas de escrita exigem nível **Gestão**.

### Agências

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/agencias` | Lista agências (filtros: `q`, `uf`, `classificacao_bacen`) |
| `GET` | `/api/agencias/<id>` | Retorna uma agência |
| `POST` | `/api/agencias` | Cria uma agência |
| `PUT` | `/api/agencias/<id>` | Atualiza uma agência |
| `DELETE` | `/api/agencias/<id>` | Remove uma agência |

### Arquivos DWG

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/agencias/<id>/dwg` | Lista arquivos DWG |
| `POST` | `/api/agencias/<id>/dwg` | Faz upload de DWG |
| `GET` | `/api/agencias/<id>/dwg/<dwg_id>/download` | Download de DWG |
| `DELETE` | `/api/agencias/<id>/dwg/<dwg_id>` | Remove um DWG |

### Vistoria do Corpo de Bombeiros

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/agencias/<id>/vistoria` | Consulta vistoria |
| `POST` | `/api/agencias/<id>/vistoria` | Cria ou atualiza vistoria |
| `POST` | `/api/agencias/<id>/vistoria/upload` | Upload do PDF da vistoria |
| `GET` | `/api/agencias/<id>/vistoria/download` | Download do PDF |

### Horários SAA

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/agencias/<id>/horarios` | Lista horários |
| `POST` | `/api/agencias/<id>/horarios` | Adiciona horário |
| `PUT` | `/api/agencias/<id>/horarios/<h_id>` | Atualiza horário |
| `DELETE` | `/api/agencias/<id>/horarios/<h_id>` | Remove horário |

### Usuários e Configurações

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/usuarios` | Lista usuários |
| `POST` | `/api/usuarios` | Cria usuário |
| `PUT` | `/api/usuarios/<id>` | Atualiza usuário |
| `DELETE` | `/api/usuarios/<id>` | Remove usuário |
| `GET` | `/api/config/limiar-idi` | Consulta limiar do IDI |
| `PUT` | `/api/config/limiar-idi` | Atualiza limiar do IDI |

---

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

---

> Desenvolvido como projeto acadêmico.
