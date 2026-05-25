import os
import re
import json
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from flask import (Flask, render_template, redirect, url_for,
                   session, request, abort, jsonify, flash, send_file)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta

# Carrega variáveis do .env em desenvolvimento local (no PythonAnywhere as vars
# são configuradas pelo painel e este bloco é ignorado silenciosamente)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_inseguro_troque_em_producao')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(BASE_DIR, 'disec.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

os.makedirs(os.path.join(BASE_DIR, 'uploads', 'dwg'), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, 'uploads', 'bombeiros'), exist_ok=True)

db = SQLAlchemy(app)

CLASSIFICACOES_BACEN = [
    'Agência',
    'Posto de Atendimento Bancário (PAB)',
    'Posto de Atendimento Eletrônico (PAE)',
    'Unidade de Atendimento Bancário (UAB)',
    'Correspondente Bancário',
]
DIAS_SEMANA = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']

# Zonas bioclimáticas brasileiras (NBR 15220) com consumo máximo de referência (kWh/m²·ano)
ZONAS_BIOCLIMATICAS = {
    1: {'descricao': 'Norte úmido (Manaus, Belém)',       'consumo_ref': 120},
    2: {'descricao': 'Nordeste litorâneo',                'consumo_ref': 110},
    3: {'descricao': 'Semiárido (Petrolina)',             'consumo_ref': 100},
    4: {'descricao': 'Centro-Oeste (Brasília, Goiânia)',  'consumo_ref':  95},
    5: {'descricao': 'Sudeste quente (SP interior)',      'consumo_ref':  90},
    6: {'descricao': 'Sul subtropical (Curitiba)',        'consumo_ref':  85},
    7: {'descricao': 'Sul temperado (Porto Alegre)',      'consumo_ref':  80},
    8: {'descricao': 'Serra Gaúcha / frio intenso',       'consumo_ref':  75},
}


class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    nome       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    nivel      = db.Column(db.String(20),  nullable=False, default='Consulta')
    ativo      = db.Column(db.Boolean, default=True)
    criado_em  = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token        = db.Column(db.String(64), unique=True, nullable=True)
    reset_token_expira = db.Column(db.DateTime, nullable=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def to_dict(self):
        return {
            'id':        self.id,
            'username':  self.username,
            'nome':      self.nome,
            'email':     self.email,
            'nivel':     self.nivel,
            'ativo':     self.ativo,
            'criado_em': self.criado_em.strftime('%d/%m/%Y') if self.criado_em else ''
        }


class Agencia(db.Model):
    __tablename__ = 'agencias'

    id         = db.Column(db.Integer, primary_key=True)
    prefixo    = db.Column(db.String(10),  unique=True, nullable=False)
    nome       = db.Column(db.String(150), nullable=False)
    municipio  = db.Column(db.String(100), nullable=False)
    uf         = db.Column(db.String(2),   nullable=False)
    logradouro = db.Column(db.String(200), nullable=True)
    numero     = db.Column(db.String(20),  nullable=True)
    bairro     = db.Column(db.String(100), nullable=True)
    cep        = db.Column(db.String(10),  nullable=True)
    telefone   = db.Column(db.String(20),  nullable=True)
    gerente    = db.Column(db.String(120), nullable=True)
    segmento   = db.Column(db.String(50),  nullable=True, default='Varejo')
    status     = db.Column(db.String(50),  nullable=True, default='Operação Normal')
    lat        = db.Column(db.Float, nullable=True)
    lng        = db.Column(db.Float, nullable=True)

    consumo_energia = db.Column(db.Float, nullable=True)
    consumo_agua    = db.Column(db.Float, nullable=True)
    carbono         = db.Column(db.Float, nullable=True)
    acessibilidade  = db.Column(db.Boolean, default=True)

    eficiencia_energetica          = db.Column(db.Float, nullable=True)
    area_util                      = db.Column(db.Float, nullable=True)
    idi                            = db.Column(db.Float, nullable=True)
    zona_bioclimatica              = db.Column(db.Integer, nullable=True)
    residuos_solidos               = db.Column(db.Float, nullable=True)
    num_colaboradores              = db.Column(db.Integer, nullable=True)
    data_ultima_vistoria_bombeiros = db.Column(db.Date, nullable=True)
    email_agencia                  = db.Column(db.String(120), nullable=True)
    cnpj                           = db.Column(db.String(20), nullable=True)
    classificacao_bacen            = db.Column(db.String(60), nullable=True)
    criado_em       = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    arquivos_dwg       = db.relationship('ArquivoDWG', back_populates='agencia', cascade='all, delete-orphan')
    horarios_saa       = db.relationship('HorarioSAA', back_populates='agencia', cascade='all, delete-orphan')
    vistoria_bombeiros = db.relationship('VistoriaBombeiros', back_populates='agencia', uselist=False, cascade='all, delete-orphan')

    @property
    def zona_bioclimatica_descricao(self):
        if self.zona_bioclimatica and self.zona_bioclimatica in ZONAS_BIOCLIMATICAS:
            return ZONAS_BIOCLIMATICAS[self.zona_bioclimatica]['descricao']
        return None

    @property
    def zona_bioclimatica_consumo_ref(self):
        if self.zona_bioclimatica and self.zona_bioclimatica in ZONAS_BIOCLIMATICAS:
            return ZONAS_BIOCLIMATICAS[self.zona_bioclimatica]['consumo_ref']
        return None

    @property
    def endereco(self):
        partes = [self.logradouro or '', self.numero or '']
        partes = [p for p in partes if p]
        linha1 = ', '.join(partes)
        linha2 = f"{self.bairro or ''}, {self.municipio} - {self.uf}".strip(', ')
        return f"{linha1} - {linha2}" if linha1 else linha2

    def to_dict(self):
        return {
            'id':               self.id,
            'prefixo':          self.prefixo,
            'nome':             self.nome,
            'municipio':        self.municipio,
            'uf':               self.uf,
            'logradouro':       self.logradouro or '',
            'numero':           self.numero or '',
            'bairro':           self.bairro or '',
            'cep':              self.cep or '',
            'telefone':         self.telefone or '',
            'gerente':          self.gerente or '',
            'segmento':         self.segmento or 'Varejo',
            'status':           self.status or 'Operação Normal',
            'lat':              self.lat,
            'lng':              self.lng,
            'consumo_energia':  self.consumo_energia,
            'consumo_agua':     self.consumo_agua,
            'acessibilidade':   self.acessibilidade,
            'eficiencia_energetica':          self.eficiencia_energetica,
            'area_util':                      self.area_util,
            'idi':                            self.idi,
            'zona_bioclimatica':              self.zona_bioclimatica,
            'zona_bioclimatica_descricao':    ZONAS_BIOCLIMATICAS[self.zona_bioclimatica]['descricao'] if self.zona_bioclimatica and self.zona_bioclimatica in ZONAS_BIOCLIMATICAS else None,
            'zona_bioclimatica_consumo_ref':  ZONAS_BIOCLIMATICAS[self.zona_bioclimatica]['consumo_ref'] if self.zona_bioclimatica and self.zona_bioclimatica in ZONAS_BIOCLIMATICAS else None,
            'residuos_solidos':               self.residuos_solidos,
            'num_colaboradores':              self.num_colaboradores,
            'data_ultima_vistoria_bombeiros': self.data_ultima_vistoria_bombeiros.strftime('%d/%m/%Y') if self.data_ultima_vistoria_bombeiros else None,
            'email_agencia':                  self.email_agencia,
            'cnpj':                           self.cnpj,
            'classificacao_bacen':            self.classificacao_bacen,
            'endereco':         self.endereco,
            'cidade':           self.municipio,
            'estado':           self.uf,
        }


class ArquivoDWG(db.Model):
    __tablename__ = 'arquivos_dwg'
    id            = db.Column(db.Integer, primary_key=True)
    agencia_id    = db.Column(db.Integer, db.ForeignKey('agencias.id', ondelete='CASCADE'), nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    nome_arquivo  = db.Column(db.String(255), nullable=False)
    tamanho_bytes = db.Column(db.Integer, nullable=False)
    enviado_em    = db.Column(db.DateTime, default=datetime.utcnow)
    agencia       = db.relationship('Agencia', back_populates='arquivos_dwg')


class HorarioSAA(db.Model):
    __tablename__ = 'horarios_saa'
    id            = db.Column(db.Integer, primary_key=True)
    agencia_id    = db.Column(db.Integer, db.ForeignKey('agencias.id', ondelete='CASCADE'), nullable=False)
    dia_semana    = db.Column(db.String(20), nullable=False)
    hora_abertura = db.Column(db.String(5),  nullable=False)
    hora_encerramento = db.Column(db.String(5), nullable=False)
    agencia       = db.relationship('Agencia', back_populates='horarios_saa')


class VistoriaBombeiros(db.Model):
    __tablename__ = 'vistorias_bombeiros'
    id              = db.Column(db.Integer, primary_key=True)
    agencia_id      = db.Column(db.Integer, db.ForeignKey('agencias.id', ondelete='CASCADE'), nullable=False, unique=True)
    protocolo       = db.Column(db.String(100), nullable=False)
    data_emissao    = db.Column(db.Date, nullable=False)
    data_validade   = db.Column(db.Date, nullable=True)
    nome_arquivo    = db.Column(db.String(255), nullable=True)
    nome_original   = db.Column(db.String(255), nullable=True)
    atualizado_em   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    agencia         = db.relationship('Agencia', back_populates='vistoria_bombeiros')


class ConfiguracaoSistema(db.Model):
    __tablename__ = 'configuracoes_sistema'
    id    = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.String(255), nullable=False)


class SolicitacaoAcesso(db.Model):
    __tablename__ = 'solicitacoes_acesso'

    id          = db.Column(db.Integer, primary_key=True)
    nome        = db.Column(db.String(120), nullable=False)
    email       = db.Column(db.String(120), nullable=False)
    justificativa = db.Column(db.Text, nullable=True)
    status      = db.Column(db.String(20), nullable=False, default='pendente')
    # pendente | aprovado | rejeitado
    token       = db.Column(db.String(64), unique=True, nullable=True)
    token_expira = db.Column(db.DateTime, nullable=True)
    criado_em   = db.Column(db.DateTime, default=datetime.utcnow)
    resolvido_em = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id':           self.id,
            'nome':         self.nome,
            'email':        self.email,
            'justificativa': self.justificativa or '',
            'status':       self.status,
            'criado_em':    self.criado_em.strftime('%d/%m/%Y %H:%M') if self.criado_em else '',
            'resolvido_em': self.resolvido_em.strftime('%d/%m/%Y %H:%M') if self.resolvido_em else None,
        }


# ── Serviço de e-mail ──────────────────────────────────────────────────────────

def _smtp_config():
    """Retorna configuração SMTP a partir das variáveis de ambiente."""
    return {
        'host':     os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
        'port':     int(os.environ.get('SMTP_PORT', 587)),
        'user':     os.environ.get('SMTP_USER', ''),
        'password': os.environ.get('SMTP_PASSWORD', ''),
        'from':     os.environ.get('SMTP_FROM', os.environ.get('SMTP_USER', '')),
    }


def enviar_email(destinatario, assunto, corpo_html):
    """Envia e-mail via SMTP. Retorna True em caso de sucesso."""
    cfg = _smtp_config()
    if not cfg['user'] or not cfg['password']:
        app.logger.warning('SMTP não configurado — e-mail não enviado.')
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = assunto
        msg['From']    = cfg['from']
        msg['To']      = destinatario
        msg.attach(MIMEText(corpo_html, 'html', 'utf-8'))

        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(cfg['user'], cfg['password'])
            smtp.sendmail(cfg['from'], [destinatario], msg.as_string())
        app.logger.info(f'E-mail enviado com sucesso para {destinatario} — assunto: {assunto}')
        return True
    except smtplib.SMTPAuthenticationError as exc:
        app.logger.error(f'Falha de autenticação SMTP ao enviar para {destinatario}: {exc}')
        return False
    except smtplib.SMTPRecipientsRefused as exc:
        app.logger.error(f'Destinatário recusado pelo servidor SMTP ({destinatario}): {exc}')
        return False
    except Exception as exc:
        app.logger.error(f'Erro ao enviar e-mail para {destinatario}: {exc}')
        return False


def _base_url():
    """Retorna a URL base da aplicação."""
    return os.environ.get('APP_BASE_URL', 'https://riseup.pythonanywhere.com')


def email_solicitacao_admin(solicitacao):
    """Notifica o admin sobre nova solicitação de acesso."""
    admin_email = os.environ.get('ADMIN_EMAIL', '')
    if not admin_email:
        return
    url_admin = f"{_base_url()}/admin#tab-solicitacoes"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0038A8;padding:24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#FCF000;margin:0;">Portal DISEC — Nova Solicitação de Acesso</h2>
      </div>
      <div style="background:#f9f9f9;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px;">
        <p style="color:#333;">Uma nova solicitação de acesso foi recebida:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
          <tr><td style="padding:8px;font-weight:bold;color:#555;width:140px;">Nome:</td>
              <td style="padding:8px;color:#333;">{solicitacao.nome}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;font-weight:bold;color:#555;">E-mail:</td>
              <td style="padding:8px;color:#333;">{solicitacao.email}</td></tr>
          <tr><td style="padding:8px;font-weight:bold;color:#555;">Justificativa:</td>
              <td style="padding:8px;color:#333;">{solicitacao.justificativa or '—'}</td></tr>
          <tr style="background:#fff;"><td style="padding:8px;font-weight:bold;color:#555;">Data:</td>
              <td style="padding:8px;color:#333;">{solicitacao.criado_em.strftime('%d/%m/%Y %H:%M')}</td></tr>
        </table>
        <a href="{url_admin}" style="display:inline-block;background:#0038A8;color:#FCF000;
           padding:12px 28px;border-radius:6px;text-decoration:none;font-weight:bold;">
          Revisar no Painel Admin
        </a>
      </div>
    </div>
    """
    enviar_email(admin_email, f'[DISEC] Nova solicitação de acesso — {solicitacao.nome}', corpo)


def email_aprovacao(solicitacao, link_definir_senha):
    """Envia link de definição de senha ao usuário aprovado."""
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0038A8;padding:24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#FCF000;margin:0;">Portal DISEC — Acesso Aprovado</h2>
      </div>
      <div style="background:#f9f9f9;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px;">
        <p style="color:#333;">Olá, <strong>{solicitacao.nome}</strong>!</p>
        <p style="color:#333;">Sua solicitação de acesso ao <strong>Portal DISEC</strong> foi aprovada.</p>
        <p style="color:#333;">Clique no botão abaixo para criar sua senha. O link é válido por <strong>24 horas</strong>.</p>
        <a href="{link_definir_senha}" style="display:inline-block;background:#0038A8;color:#FCF000;
           padding:14px 32px;border-radius:6px;text-decoration:none;font-weight:bold;margin:16px 0;">
          Criar Minha Senha
        </a>
        <p style="color:#888;font-size:0.85rem;">Se não solicitou acesso, ignore este e-mail.</p>
        <p style="color:#aaa;font-size:0.8rem;">Link: {link_definir_senha}</p>
      </div>
    </div>
    """
    enviar_email(solicitacao.email, '[DISEC] Acesso aprovado — Crie sua senha', corpo)


def email_rejeicao(solicitacao):
    """Notifica o usuário que a solicitação foi rejeitada."""
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0038A8;padding:24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#FCF000;margin:0;">Portal DISEC — Solicitação de Acesso</h2>
      </div>
      <div style="background:#f9f9f9;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px;">
        <p style="color:#333;">Olá, <strong>{solicitacao.nome}</strong>.</p>
        <p style="color:#333;">Infelizmente sua solicitação de acesso ao <strong>Portal DISEC</strong>
           não foi aprovada neste momento.</p>
        <p style="color:#333;">Em caso de dúvidas, entre em contato com a equipe DISEC.</p>
      </div>
    </div>
    """
    enviar_email(solicitacao.email, '[DISEC] Solicitação de acesso não aprovada', corpo)


def email_boas_vindas(usuario, senha_temporaria):
    """Envia e-mail de boas-vindas com credenciais ao usuário criado pelo admin."""
    url_login = f"{_base_url()}/login"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0038A8;padding:24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#FCF000;margin:0;">Portal DISEC — Bem-vindo(a)!</h2>
      </div>
      <div style="background:#f9f9f9;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px;">
        <p style="color:#333;">Olá, <strong>{usuario.nome}</strong>!</p>
        <p style="color:#333;">Sua conta no <strong>Portal DISEC</strong> foi criada com sucesso.
           Utilize as credenciais abaixo para acessar o sistema:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
          <tr>
            <td style="padding:10px;font-weight:bold;color:#555;width:140px;background:#f0f0f0;">Usuário:</td>
            <td style="padding:10px;color:#333;background:#fff;font-family:monospace;">{usuario.username}</td>
          </tr>
          <tr>
            <td style="padding:10px;font-weight:bold;color:#555;background:#f0f0f0;">Senha temporária:</td>
            <td style="padding:10px;color:#333;background:#fff;font-family:monospace;">{senha_temporaria}</td>
          </tr>
          <tr>
            <td style="padding:10px;font-weight:bold;color:#555;background:#f0f0f0;">Nível de acesso:</td>
            <td style="padding:10px;color:#333;background:#fff;">{usuario.nivel}</td>
          </tr>
        </table>
        <p style="color:#c0392b;font-size:0.9rem;">
          ⚠️ Por segurança, altere sua senha após o primeiro acesso.
        </p>
        <a href="{url_login}" style="display:inline-block;background:#0038A8;color:#FCF000;
           padding:14px 32px;border-radius:6px;text-decoration:none;font-weight:bold;margin:16px 0;">
          Acessar o Portal
        </a>
        <p style="color:#888;font-size:0.85rem;">Se você não esperava este e-mail, entre em contato com a equipe DISEC.</p>
      </div>
    </div>
    """
    enviar_email(usuario.email, '[DISEC] Suas credenciais de acesso', corpo)


def email_recuperacao_senha(usuario, link_redefinir):
    """Envia e-mail com link para redefinição de senha."""
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#0038A8;padding:24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#FCF000;margin:0;">Portal DISEC — Redefinição de Senha</h2>
      </div>
      <div style="background:#f9f9f9;padding:24px;border:1px solid #e0e0e0;border-radius:0 0 8px 8px;">
        <p style="color:#333;">Olá, <strong>{usuario.nome}</strong>!</p>
        <p style="color:#333;">Recebemos uma solicitação para redefinir a senha da sua conta no <strong>Portal DISEC</strong>.</p>
        <p style="color:#333;">Clique no botão abaixo para criar uma nova senha. O link é válido por <strong>1 hora</strong>.</p>
        <a href="{link_redefinir}" style="display:inline-block;background:#0038A8;color:#FCF000;
           padding:14px 32px;border-radius:6px;text-decoration:none;font-weight:bold;margin:16px 0;">
          Redefinir Minha Senha
        </a>
        <p style="color:#888;font-size:0.85rem;">Se você não solicitou a redefinição de senha, ignore este e-mail. Sua senha permanece a mesma.</p>
        <p style="color:#aaa;font-size:0.8rem;">Link: {link_redefinir}</p>
      </div>
    </div>
    """
    enviar_email(usuario.email, '[DISEC] Redefinição de senha', corpo)


def calcular_eficiencia_energetica(consumo_energia, area_util):
    """Calcula eficiência energética mensal em kWh/m².
    Retorna round(consumo / area, 2) ou None se area_util for zero/None.
    """
    if not consumo_energia or not area_util:
        return None
    return round(consumo_energia / area_util, 2)


def calcular_idi_por_zona(consumo_energia, area_util, zona_bioclimatica):
    """Calcula IDI contínuo (1.0–5.0) ajustado pela zona bioclimática.

    Fórmula:
      efic_mensal = consumo_energia / area_util   [kWh/m²·mês]
      ratio       = efic_mensal / consumo_ref_zona

    Mapeamento linear contínuo por faixa de ratio:
      ratio <= 0.00  → IDI 5.0
      ratio  0.00–0.60 → IDI 5.0–4.0  (linear)
      ratio  0.60–0.75 → IDI 4.0–3.0  (linear)
      ratio  0.75–0.90 → IDI 3.0–2.0  (linear)
      ratio  0.90–1.00 → IDI 2.0–1.0  (linear)
      ratio >= 1.00  → IDI 1.0

    Retorna None se faltar consumo, área ou zona.
    """
    if not consumo_energia or not area_util or not zona_bioclimatica:
        return None
    zona = ZONAS_BIOCLIMATICAS.get(zona_bioclimatica)
    if not zona:
        return None
    efic_mensal = consumo_energia / area_util
    ratio       = efic_mensal / zona['consumo_ref']

    if ratio >= 1.00:
        idi = 1.0
    elif ratio >= 0.90:
        # 0.90–1.00 → 2.0–1.0
        idi = 2.0 - ((ratio - 0.90) / 0.10) * 1.0
    elif ratio >= 0.75:
        # 0.75–0.90 → 3.0–2.0
        idi = 3.0 - ((ratio - 0.75) / 0.15) * 1.0
    elif ratio >= 0.60:
        # 0.60–0.75 → 4.0–3.0
        idi = 4.0 - ((ratio - 0.60) / 0.15) * 1.0
    else:
        # 0.00–0.60 → 5.0–4.0
        idi = 5.0 - (ratio / 0.60) * 1.0

    return round(max(1.0, min(5.0, idi)), 2)


def validar_idi(valor):
    """Retorna True se valor está entre 1 e 5."""
    try:
        v = float(valor)
        return 1.0 <= v <= 5.0
    except (TypeError, ValueError):
        return False


def validar_cnpj_formato(cnpj):
    """Valida formato XX.XXX.XXX/XXXX-XX."""
    if not cnpj:
        return False
    return bool(re.match(r'^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$', cnpj))


def cor_marcador_idi(idi, limiar):
    """Retorna cor hex para marcador de mapa baseado no IDI.
    - None -> '#6B7280' (cinza)
    - idi >= limiar -> '#0038A8' (azul — tolerável/bom)
    - idi < limiar -> '#E11D48' (vermelho — crítico/alerta)
    """
    if idi is None:
        return '#6B7280'
    if idi >= limiar:
        return '#0038A8'
    return '#E11D48'


def is_vistoria_vencida(data_validade, data_atual):
    """Retorna True se data_validade < data_atual."""
    if data_validade is None:
        return False
    return data_validade < data_atual


def seed_db():
    """Popula o banco com dados iniciais se estiver vazio."""
    if Usuario.query.count() == 0:
        admin = Usuario(
            username='igor.barbosa',
            nome='Igor Barbosa',
            email='igor@bb.com.br',
            nivel='Gestão',
            ativo=True
        )
        admin.set_senha(os.environ.get('ADMIN_INITIAL_PASSWORD', 'Troque@Esta#Senha1'))

        visitante = Usuario(
            username='visitante',
            nome='Usuário Visitante',
            email='visitante@bb.com.br',
            nivel='Consulta',
            ativo=True
        )
        visitante.set_senha(os.environ.get('VISITANTE_INITIAL_PASSWORD', 'Troque@Esta#Senha2'))

        db.session.add_all([admin, visitante])
        db.session.commit()

    if Agencia.query.count() == 0:
        json_path = os.path.join(BASE_DIR, 'data', 'agencias.json')
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                agencias_json = json.load(f)
            for ag in agencias_json:
                agencia = Agencia(
                    prefixo=str(ag.get('prefixo', '')),
                    nome=ag.get('nome', ''),
                    municipio=ag.get('municipio', ''),
                    uf=ag.get('uf', ''),
                    logradouro=ag.get('logradouro'),
                    numero=ag.get('numero'),
                    bairro=ag.get('bairro'),
                    cep=ag.get('cep'),
                    telefone=ag.get('telefone'),
                    gerente=ag.get('gerente'),
                    segmento=ag.get('segmento', 'Varejo').replace('Agronegocio', 'Agronegócio'),
                    status=ag.get('status', 'Operação Normal').replace('Operacao Normal', 'Operação Normal'),
                    acessibilidade=ag.get('acessibilidade', True),
                    lat=ag.get('lat'),
                    lng=ag.get('lng'),
                    consumo_energia=ag.get('consumo_energia'),
                    consumo_agua=ag.get('consumo_agua'),
                    carbono=ag.get('carbono'),
                )
                db.session.add(agencia)
            db.session.commit()
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if not ConfiguracaoSistema.query.filter_by(chave='limiar_idi').first():
        db.session.add(ConfiguracaoSistema(chave='limiar_idi', valor='3.0'))
        db.session.commit()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def gestao_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('user_level') != 'Gestão':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def get_template_context():
    return {
        'user_level': session.get('user_level'),
        'user_name':  session.get('user_name'),
    }


def get_stats():
    from sqlalchemy import func as sqlfunc

    agencias = Agencia.query.all()
    total    = len(agencias)
    hoje     = date.today()

    em_reforma = sum(1 for a in agencias if a.status == 'Em Reforma')
    fechadas   = sum(1 for a in agencias if a.status == 'Fechada')
    operando   = sum(1 for a in agencias if a.status not in ('Em Reforma', 'Fechada'))

    limiar_cfg = ConfiguracaoSistema.query.filter_by(chave='limiar_idi').first()
    limiar_idi = float(limiar_cfg.valor) if limiar_cfg else 3.0
    com_idi    = [a for a in agencias if a.idi is not None]
    idi_critico = sum(1 for a in com_idi if a.idi < limiar_idi)
    idi_medio  = round(sum(a.idi for a in com_idi) / len(com_idi), 1) if com_idi else None

    com_energia = [a.consumo_energia for a in agencias if a.consumo_energia]
    com_agua    = [a.consumo_agua    for a in agencias if a.consumo_agua]
    com_efic    = [a.eficiencia_energetica for a in agencias if a.eficiencia_energetica]
    com_res     = [a.residuos_solidos for a in agencias if a.residuos_solidos]
    total_energia = round(sum(com_energia) / 1000, 1) if com_energia else 0   # MWh
    total_agua    = round(sum(com_agua), 0) if com_agua else 0                 # m³
    media_efic    = round(sum(com_efic) / len(com_efic), 2) if com_efic else None
    total_residuos = round(sum(com_res), 0) if com_res else 0                  # kg

    total_colab   = sum(a.num_colaboradores for a in agencias if a.num_colaboradores)
    acessiveis    = sum(1 for a in agencias if a.acessibilidade)
    pct_acessivel = round(acessiveis / total * 100) if total else 0

    com_vistoria  = [a for a in agencias if a.vistoria_bombeiros]
    vencidas      = sum(
        1 for a in com_vistoria
        if a.vistoria_bombeiros.data_validade and a.vistoria_bombeiros.data_validade < hoje
    )
    sem_vistoria  = total - len(com_vistoria)

    segmentos = {}
    for a in agencias:
        seg = a.segmento or 'Varejo'
        seg = seg.replace('Agronegocio', 'Agronegócio')
        segmentos[seg] = segmentos.get(seg, 0) + 1

    bacen_dist = {}
    for a in agencias:
        cls = a.classificacao_bacen or 'Não classificada'
        bacen_dist[cls] = bacen_dist.get(cls, 0) + 1

    criticos = sorted(com_idi, key=lambda a: a.idi)[:5]
    top_criticos = [{'prefixo': a.prefixo, 'nome': a.nome, 'idi': a.idi,
                     'municipio': a.municipio, 'uf': a.uf} for a in criticos]

    # Ranking eficiência energética por UF (top 5 piores = maior consumo/m²)
    com_efic_ags = [(a.uf, a.eficiencia_energetica) for a in agencias if a.eficiencia_energetica]
    uf_efic = {}
    for uf, efic in com_efic_ags:
        if uf not in uf_efic:
            uf_efic[uf] = []
        uf_efic[uf].append(efic)
    ranking_efic = sorted(
        [{'uf': uf, 'media': round(sum(v)/len(v), 2)} for uf, v in uf_efic.items()],
        key=lambda x: x['media'], reverse=True
    )[:6]

    # Listas detalhadas para as tabelas do dashboard
    idi_critico_lista = sorted(
        [a for a in com_idi if a.idi < limiar_idi],
        key=lambda a: a.idi
    )

    em_reforma_lista = [a for a in agencias if a.status == 'Em Reforma']

    vencidas_lista = []
    for a in com_vistoria:
        v = a.vistoria_bombeiros
        if v.data_validade and v.data_validade < hoje:
            dias_vencida = (hoje - v.data_validade).days
            vencidas_lista.append({
                'prefixo':       a.prefixo,
                'nome':          a.nome,
                'municipio':     a.municipio,
                'uf':            a.uf,
                'protocolo':     v.protocolo,
                'data_validade': v.data_validade.strftime('%d/%m/%Y'),
                'dias_vencida':  dias_vencida,
            })
    vencidas_lista.sort(key=lambda x: x['dias_vencida'], reverse=True)

    top_energia_lista = sorted(
        [a for a in agencias if a.consumo_energia],
        key=lambda a: a.consumo_energia,
        reverse=True
    )[:5]
    top_energia_lista = [
        {
            'prefixo': a.prefixo,
            'nome':    a.nome,
            'uf':      a.uf,
            'consumo': a.consumo_energia,
            'efic':    a.eficiencia_energetica,
        }
        for a in top_energia_lista
    ]

    # Distribuição por zona bioclimática com IDI médio e eficiência média por zona
    zona_dist = {}
    for a in agencias:
        z = a.zona_bioclimatica
        if z and z in ZONAS_BIOCLIMATICAS:
            if z not in zona_dist:
                zona_dist[z] = {
                    'zona':        z,
                    'descricao':   ZONAS_BIOCLIMATICAS[z]['descricao'],
                    'consumo_ref': ZONAS_BIOCLIMATICAS[z]['consumo_ref'],
                    'total':       0,
                    'idi_vals':    [],
                    'efic_vals':   [],
                }
            zona_dist[z]['total'] += 1
            if a.idi is not None:
                zona_dist[z]['idi_vals'].append(a.idi)
            # Eficiência mensal: usa campo calculado ou deriva de consumo/área
            efic_mensal = a.eficiencia_energetica
            if efic_mensal is None and a.consumo_energia and a.area_util:
                efic_mensal = round(a.consumo_energia / a.area_util, 2)
            if efic_mensal is not None:
                zona_dist[z]['efic_vals'].append(efic_mensal)

    zonas_lista = []
    for z_num in sorted(zona_dist.keys()):
        entry = zona_dist[z_num]
        idi_vals  = entry.pop('idi_vals')
        efic_vals = entry.pop('efic_vals')
        entry['idi_medio']  = round(sum(idi_vals)  / len(idi_vals),  2) if idi_vals  else None
        entry['efic_media'] = round(sum(efic_vals) / len(efic_vals), 2) if efic_vals else None
        zonas_lista.append(entry)

    sem_zona = sum(1 for a in agencias if not a.zona_bioclimatica)

    return {
        'total':              total,
        'em_reforma':         em_reforma,
        'fechadas':           fechadas,
        'operando':           operando,
        'limiar_idi':         limiar_idi,
        'idi_critico':        idi_critico,
        'idi_medio':          idi_medio,
        'total_energia':      total_energia,
        'total_agua':         int(total_agua),
        'media_efic':         media_efic,
        'total_residuos':     int(total_residuos),
        'total_colab':        total_colab,
        'pct_acessivel':      pct_acessivel,
        'acessiveis':         acessiveis,
        'vencidas':           vencidas,
        'sem_vistoria':       sem_vistoria,
        'segmentos':          segmentos,
        'bacen_dist':         bacen_dist,
        'top_criticos':       top_criticos,
        'idi_critico_lista':  idi_critico_lista,
        'em_reforma_lista':   em_reforma_lista,
        'vencidas_lista':     vencidas_lista,
        'top_energia_lista':  top_energia_lista,
        'ranking_efic':       ranking_efic,
        'zonas_lista':        zonas_lista,
        'sem_zona':           sem_zona,
    }


def get_alerts():
    """Retorna apenas os dados de alerta necessários para a tela inicial."""
    agencias = Agencia.query.all()
    hoje = date.today()

    limiar_cfg = ConfiguracaoSistema.query.filter_by(chave='limiar_idi').first()
    limiar_idi = float(limiar_cfg.valor) if limiar_cfg else 3.0

    com_idi     = [a for a in agencias if a.idi is not None]
    idi_critico = sum(1 for a in com_idi if a.idi < limiar_idi)

    com_vistoria = [a for a in agencias if a.vistoria_bombeiros]
    vencidas = sum(
        1 for a in com_vistoria
        if a.vistoria_bombeiros.data_validade and a.vistoria_bombeiros.data_validade < hoje
    )

    return {
        'idi_critico': idi_critico,
        'limiar_idi':  limiar_idi,
        'vencidas':    vencidas,
    }


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        senha    = request.form.get('password', '')

        user = Usuario.query.filter_by(username=username, ativo=True).first()

        if user and user.check_senha(senha):
            session.clear()
            session['user_id']    = user.id
            session['user_name']  = user.nome
            session['user_level'] = user.nivel
            return redirect(url_for('index'))

        return render_template('login.html', erro=True)

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    ctx = get_template_context()
    ctx['page_title'] = 'Início'
    ctx['alerts']     = get_alerts()
    return render_template('index.html', **ctx)


@app.route('/agencias')
@login_required
def agencias():
    ctx = get_template_context()
    ctx['page_title']       = 'Consulta Nacional de Agências'
    ctx['google_maps_key']  = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    return render_template('agencias.html', **ctx)


@app.route('/informacoes')
@login_required
def detalhes_index():
    """Tela de busca/filtro de agências — Informações das Agências."""
    ctx = get_template_context()
    ctx['page_title'] = 'Informações das Agências'
    return render_template('informacoes.html', **ctx)


@app.route('/detalhes/<prefixo>')
@login_required
def detalhes(prefixo):
    agencia = Agencia.query.filter_by(prefixo=prefixo).first_or_404()
    ctx = get_template_context()
    ctx['page_title']      = f"Informações — Agência {prefixo}"
    ctx['agencia']         = agencia
    ctx['google_maps_key'] = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    return render_template('detalhes.html', **ctx)


@app.route('/dashboard')
@login_required
def dashboard():
    stats = get_stats()
    ctx = get_template_context()
    ctx['page_title']      = 'Dashboard Estratégico DISEC'
    ctx['stats']           = stats
    ctx['google_maps_key'] = os.environ.get('GOOGLE_MAPS_API_KEY', '')
    return render_template('dashboard.html', **ctx)


@app.route('/admin')
@gestao_required
def admin():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    ctx = get_template_context()
    ctx['page_title'] = 'Gestão DISEC'
    ctx['usuarios']   = usuarios
    return render_template('admin.html', **ctx)


@app.route('/api/agencias')
@login_required
def api_agencias():
    filtro = request.args.get('q', '').strip().lower()
    uf     = request.args.get('uf', '').strip().upper()

    query = Agencia.query

    if filtro:
        query = query.filter(
            db.or_(
                Agencia.nome.ilike(f'%{filtro}%'),
                Agencia.municipio.ilike(f'%{filtro}%'),
                Agencia.prefixo.ilike(f'%{filtro}%'),
                Agencia.bairro.ilike(f'%{filtro}%'),
            )
        )
    if uf:
        query = query.filter_by(uf=uf)
    classificacao_bacen = request.args.get('classificacao_bacen', '').strip()
    if classificacao_bacen:
        query = query.filter_by(classificacao_bacen=classificacao_bacen)

    agencias = query.order_by(Agencia.nome).all()
    return jsonify([ag.to_dict() for ag in agencias])


@app.route('/api/agencias/<int:agencia_id>', methods=['GET'])
@login_required
def api_agencia_get(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    return jsonify(ag.to_dict())


@app.route('/api/agencias', methods=['POST'])
@gestao_required
def api_agencias_criar():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    prefixo = str(data.get('prefixo', '')).strip()
    nome    = str(data.get('nome', '')).strip()
    municipio = str(data.get('municipio', '')).strip()
    uf      = str(data.get('uf', '')).strip().upper()

    if not all([prefixo, nome, municipio, uf]):
        return jsonify({'erro': 'Prefixo, nome, município e UF são obrigatórios'}), 400

    if Agencia.query.filter_by(prefixo=prefixo).first():
        return jsonify({'erro': f'Prefixo {prefixo} já cadastrado'}), 409

    cnpj = data.get('cnpj')
    if cnpj and not validar_cnpj_formato(cnpj):
        return jsonify({'erro': 'CNPJ inválido. Use o formato XX.XXX.XXX/XXXX-XX.'}), 400

    area_util        = float(data['area_util']) if data.get('area_util') not in (None, '') else None
    consumo_energia  = float(data['consumo_energia']) if data.get('consumo_energia') not in (None, '') else None
    zona_bioclimatica = int(data['zona_bioclimatica']) if data.get('zona_bioclimatica') not in (None, '') else None

    if zona_bioclimatica is not None and zona_bioclimatica not in ZONAS_BIOCLIMATICAS:
        return jsonify({'erro': 'Zona bioclimática inválida. Use um valor entre 1 e 8.'}), 400

    eficiencia_energetica = calcular_eficiencia_energetica(consumo_energia, area_util)

    # IDI é informado manualmente pela engenharia — não é calculado automaticamente
    idi_raw = data.get('idi')
    idi = float(idi_raw) if idi_raw not in (None, '') else None
    if idi is not None and not validar_idi(idi):
        return jsonify({'erro': 'IDI inválido. Informe um valor entre 1,0 e 5,0.'}), 400

    ag = Agencia(
        prefixo=prefixo, nome=nome, municipio=municipio, uf=uf,
        logradouro=data.get('logradouro'), numero=data.get('numero'),
        bairro=data.get('bairro'), cep=data.get('cep'),
        telefone=data.get('telefone'), gerente=data.get('gerente'),
        segmento=data.get('segmento', 'Varejo'),
        status=data.get('status', 'Operação Normal'),
        lat=data.get('lat') or None, lng=data.get('lng') or None,
        consumo_energia=consumo_energia,
        consumo_agua=float(data['consumo_agua']) if data.get('consumo_agua') not in (None, '') else None,
        acessibilidade=bool(data.get('acessibilidade', True)),
        email_agencia=data.get('email_agencia') or None,
        cnpj=cnpj or None,
        area_util=area_util,
        zona_bioclimatica=zona_bioclimatica,
        idi=idi,
        eficiencia_energetica=eficiencia_energetica,
        residuos_solidos=float(data['residuos_solidos']) if data.get('residuos_solidos') not in (None, '') else None,
        num_colaboradores=int(data['num_colaboradores']) if data.get('num_colaboradores') not in (None, '') else None,
        classificacao_bacen=data.get('classificacao_bacen') or None,
    )
    db.session.add(ag)
    db.session.commit()
    return jsonify(ag.to_dict()), 201


@app.route('/api/agencias/<int:agencia_id>', methods=['PUT'])
@gestao_required
def api_agencias_editar(agencia_id):
    ag   = Agencia.query.get_or_404(agencia_id)
    data = request.get_json(force=True)
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    campos_str = ['nome', 'municipio', 'logradouro', 'numero', 'bairro',
                  'cep', 'telefone', 'gerente', 'segmento', 'status']
    for campo in campos_str:
        if campo in data:
            setattr(ag, campo, str(data[campo]).strip() or None)

    if 'uf' in data:
        ag.uf = str(data['uf']).strip().upper()
    if 'lat' in data:
        ag.lat = float(data['lat']) if data['lat'] not in (None, '') else None
    if 'lng' in data:
        ag.lng = float(data['lng']) if data['lng'] not in (None, '') else None
    if 'consumo_energia' in data:
        ag.consumo_energia = float(data['consumo_energia']) if data['consumo_energia'] not in (None, '') else None
    if 'consumo_agua' in data:
        ag.consumo_agua = float(data['consumo_agua']) if data['consumo_agua'] not in (None, '') else None
    if 'acessibilidade' in data:
        ag.acessibilidade = bool(data['acessibilidade'])
    if 'email_agencia' in data:
        ag.email_agencia = str(data['email_agencia']).strip() or None
    if 'cnpj' in data:
        cnpj = str(data['cnpj']).strip() if data['cnpj'] else None
        if cnpj and not validar_cnpj_formato(cnpj):
            return jsonify({'erro': 'CNPJ inválido. Use o formato XX.XXX.XXX/XXXX-XX.'}), 400
        ag.cnpj = cnpj
    if 'area_util' in data:
        ag.area_util = float(data['area_util']) if data['area_util'] not in (None, '') else None
    if 'zona_bioclimatica' in data:
        if data['zona_bioclimatica'] not in (None, ''):
            try:
                zb = int(data['zona_bioclimatica'])
                if zb not in ZONAS_BIOCLIMATICAS:
                    return jsonify({'erro': 'Zona bioclimática inválida. Use um valor entre 1 e 8.'}), 400
                ag.zona_bioclimatica = zb
            except (TypeError, ValueError):
                return jsonify({'erro': 'Zona bioclimática deve ser um número inteiro entre 1 e 8.'}), 400
        else:
            ag.zona_bioclimatica = None
    if 'residuos_solidos' in data:
        ag.residuos_solidos = float(data['residuos_solidos']) if data['residuos_solidos'] not in (None, '') else None
    if 'num_colaboradores' in data:
        ag.num_colaboradores = int(data['num_colaboradores']) if data['num_colaboradores'] not in (None, '') else None
    if 'classificacao_bacen' in data:
        ag.classificacao_bacen = str(data['classificacao_bacen']).strip() or None

    # IDI é informado manualmente pela engenharia — não é recalculado automaticamente
    if 'idi' in data:
        idi_raw = data['idi']
        idi = float(idi_raw) if idi_raw not in (None, '') else None
        if idi is not None and not validar_idi(idi):
            return jsonify({'erro': 'IDI inválido. Informe um valor entre 1,0 e 5,0.'}), 400
        ag.idi = idi

    # Recalcula apenas eficiência energética automaticamente
    ag.eficiencia_energetica = calcular_eficiencia_energetica(ag.consumo_energia, ag.area_util)

    ag.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(ag.to_dict())


@app.route('/api/agencias/<int:agencia_id>', methods=['DELETE'])
@gestao_required
def api_agencias_deletar(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    db.session.delete(ag)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/recalcular-eficiencia', methods=['POST'])
@gestao_required
def api_recalcular_eficiencia():
    """Recalcula eficiência energética de todas as agências. O IDI não é alterado (informado manualmente)."""
    agencias = Agencia.query.all()
    atualizadas = 0
    for ag in agencias:
        nova_efic = calcular_eficiencia_energetica(ag.consumo_energia, ag.area_util)
        if nova_efic != ag.eficiencia_energetica:
            ag.eficiencia_energetica = nova_efic
            atualizadas += 1
    db.session.commit()
    return jsonify({'ok': True, 'atualizadas': atualizadas})


@app.route('/api/agencias/<int:agencia_id>/dwg', methods=['GET'])
@login_required
def api_dwg_listar(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    arquivos = ArquivoDWG.query.filter_by(agencia_id=agencia_id).order_by(ArquivoDWG.enviado_em.desc()).all()
    return jsonify([{
        'id':            a.id,
        'nome_original': a.nome_original,
        'tamanho_bytes': a.tamanho_bytes,
        'enviado_em':    a.enviado_em.strftime('%d/%m/%Y') if a.enviado_em else '',
    } for a in arquivos])


@app.route('/api/agencias/<int:agencia_id>/dwg', methods=['POST'])
@gestao_required
def api_dwg_upload(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)

    if 'arquivo' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    arquivo = request.files['arquivo']
    if not arquivo.filename:
        return jsonify({'erro': 'Nenhum arquivo selecionado'}), 400

    if not arquivo.filename.lower().endswith('.dwg'):
        return jsonify({'erro': 'Apenas arquivos no formato DWG são aceitos.'}), 400

    nome_seguro = secure_filename(arquivo.filename)
    if not nome_seguro or nome_seguro.lower() == 'dwg':
        nome_seguro = f"{uuid.uuid4().hex}.dwg"

    conteudo = arquivo.read()
    tamanho = len(conteudo)
    if tamanho > 50 * 1024 * 1024:
        return jsonify({'erro': 'O arquivo excede o limite de 50 MB.'}), 400

    nome_uuid = f"{uuid.uuid4().hex}_{nome_seguro}"
    pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'dwg', str(agencia_id))
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome_uuid)
    with open(caminho, 'wb') as f:
        f.write(conteudo)

    registro = ArquivoDWG(
        agencia_id=agencia_id,
        nome_original=arquivo.filename,
        nome_arquivo=nome_uuid,
        tamanho_bytes=tamanho,
    )
    db.session.add(registro)
    db.session.commit()

    return jsonify({
        'id':            registro.id,
        'nome_original': registro.nome_original,
        'tamanho_bytes': registro.tamanho_bytes,
        'enviado_em':    registro.enviado_em.strftime('%d/%m/%Y') if registro.enviado_em else '',
    }), 201


@app.route('/api/agencias/<int:agencia_id>/dwg/<int:dwg_id>/download', methods=['GET'])
@login_required
def api_dwg_download(agencia_id, dwg_id):
    ag = Agencia.query.get_or_404(agencia_id)
    arquivo = ArquivoDWG.query.filter_by(id=dwg_id, agencia_id=agencia_id).first_or_404()
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'dwg', str(agencia_id), arquivo.nome_arquivo)
    if not os.path.exists(caminho):
        return jsonify({'erro': 'Arquivo não encontrado no servidor'}), 404
    return send_file(
        caminho,
        as_attachment=True,
        download_name=arquivo.nome_original,
    )


@app.route('/api/agencias/<int:agencia_id>/dwg/<int:dwg_id>', methods=['DELETE'])
@gestao_required
def api_dwg_deletar(agencia_id, dwg_id):
    ag = Agencia.query.get_or_404(agencia_id)
    arquivo = ArquivoDWG.query.filter_by(id=dwg_id, agencia_id=agencia_id).first_or_404()

    caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'dwg', str(agencia_id), arquivo.nome_arquivo)
    if os.path.exists(caminho):
        os.remove(caminho)
    db.session.delete(arquivo)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/agencias/<int:agencia_id>/horarios', methods=['GET'])
@login_required
def api_horarios_listar(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)

    horarios = HorarioSAA.query.filter_by(agencia_id=agencia_id).all()
    def ordem_dia(h):
        try:
            return DIAS_SEMANA.index(h.dia_semana)
        except ValueError:
            return 99
    horarios_sorted = sorted(horarios, key=ordem_dia)
    return jsonify([{
        'id':               h.id,
        'dia_semana':       h.dia_semana,
        'hora_abertura':    h.hora_abertura,
        'hora_encerramento': h.hora_encerramento,
    } for h in horarios_sorted])


@app.route('/api/agencias/<int:agencia_id>/horarios', methods=['POST'])
@gestao_required
def api_horarios_criar(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    data = request.get_json(force=True)
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    dia_semana = str(data.get('dia_semana', '')).strip()
    hora_abertura = str(data.get('hora_abertura', '')).strip()
    hora_encerramento = str(data.get('hora_encerramento', '')).strip()

    if not all([dia_semana, hora_abertura, hora_encerramento]):
        return jsonify({'erro': 'Dia da semana, hora de abertura e hora de encerramento são obrigatórios'}), 400

    if dia_semana not in DIAS_SEMANA:
        return jsonify({'erro': f'Dia da semana inválido. Use: {", ".join(DIAS_SEMANA)}'}), 400

    if hora_encerramento <= hora_abertura:
        return jsonify({'erro': 'O horário de encerramento deve ser posterior ao horário de abertura.'}), 400

    horario = HorarioSAA(
        agencia_id=agencia_id,
        dia_semana=dia_semana,
        hora_abertura=hora_abertura,
        hora_encerramento=hora_encerramento,
    )
    db.session.add(horario)
    db.session.commit()
    return jsonify({
        'id':               horario.id,
        'dia_semana':       horario.dia_semana,
        'hora_abertura':    horario.hora_abertura,
        'hora_encerramento': horario.hora_encerramento,
    }), 201


@app.route('/api/agencias/<int:agencia_id>/horarios/<int:h_id>', methods=['PUT'])
@gestao_required
def api_horarios_editar(agencia_id, h_id):
    ag = Agencia.query.get_or_404(agencia_id)
    horario = HorarioSAA.query.filter_by(id=h_id, agencia_id=agencia_id).first_or_404()
    data = request.get_json(force=True)
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    hora_abertura = str(data.get('hora_abertura', horario.hora_abertura)).strip()
    hora_encerramento = str(data.get('hora_encerramento', horario.hora_encerramento)).strip()
    dia_semana = str(data.get('dia_semana', horario.dia_semana)).strip()

    if dia_semana not in DIAS_SEMANA:
        return jsonify({'erro': f'Dia da semana inválido. Use: {", ".join(DIAS_SEMANA)}'}), 400

    if hora_encerramento <= hora_abertura:
        return jsonify({'erro': 'O horário de encerramento deve ser posterior ao horário de abertura.'}), 400

    horario.dia_semana = dia_semana
    horario.hora_abertura = hora_abertura
    horario.hora_encerramento = hora_encerramento
    db.session.commit()
    return jsonify({
        'id':               horario.id,
        'dia_semana':       horario.dia_semana,
        'hora_abertura':    horario.hora_abertura,
        'hora_encerramento': horario.hora_encerramento,
    })


@app.route('/api/agencias/<int:agencia_id>/horarios/<int:h_id>', methods=['DELETE'])
@gestao_required
def api_horarios_deletar(agencia_id, h_id):
    ag = Agencia.query.get_or_404(agencia_id)
    horario = HorarioSAA.query.filter_by(id=h_id, agencia_id=agencia_id).first_or_404()
    db.session.delete(horario)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/agencias/<int:agencia_id>/vistoria', methods=['GET'])
@login_required
def api_vistoria_get(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    v = ag.vistoria_bombeiros
    if not v:
        return jsonify({'erro': 'Vistoria não cadastrada'}), 404
    return jsonify({
        'id':            v.id,
        'protocolo':     v.protocolo,
        'data_emissao':  v.data_emissao.strftime('%Y-%m-%d') if v.data_emissao else None,
        'data_validade': v.data_validade.strftime('%Y-%m-%d') if v.data_validade else None,
        'nome_original': v.nome_original,
        'atualizado_em': v.atualizado_em.strftime('%d/%m/%Y %H:%M') if v.atualizado_em else None,
        'vencida':       is_vistoria_vencida(v.data_validade, date.today()) if v.data_validade else False,
    })


@app.route('/api/agencias/<int:agencia_id>/vistoria', methods=['POST'])
@gestao_required
def api_vistoria_upsert(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    data = request.get_json(force=True)
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    protocolo = str(data.get('protocolo', '')).strip()
    data_emissao_str = str(data.get('data_emissao', '')).strip()

    if not protocolo or not data_emissao_str:
        return jsonify({'erro': 'Protocolo e data de emissão são obrigatórios'}), 400

    try:
        data_emissao = date.fromisoformat(data_emissao_str)
    except ValueError:
        return jsonify({'erro': 'Formato de data inválido. Use YYYY-MM-DD'}), 400

    data_validade = None
    data_validade_str = str(data.get('data_validade', '')).strip()
    if data_validade_str:
        try:
            data_validade = date.fromisoformat(data_validade_str)
        except ValueError:
            return jsonify({'erro': 'Formato de data de validade inválido. Use YYYY-MM-DD'}), 400

    v = ag.vistoria_bombeiros
    if v:
        v.protocolo = protocolo
        v.data_emissao = data_emissao
        v.data_validade = data_validade
        v.atualizado_em = datetime.utcnow()
    else:
        v = VistoriaBombeiros(
            agencia_id=agencia_id,
            protocolo=protocolo,
            data_emissao=data_emissao,
            data_validade=data_validade,
        )
        db.session.add(v)

    db.session.commit()
    return jsonify({
        'id':            v.id,
        'protocolo':     v.protocolo,
        'data_emissao':  v.data_emissao.strftime('%Y-%m-%d') if v.data_emissao else None,
        'data_validade': v.data_validade.strftime('%Y-%m-%d') if v.data_validade else None,
        'nome_original': v.nome_original,
        'atualizado_em': v.atualizado_em.strftime('%d/%m/%Y %H:%M') if v.atualizado_em else None,
        'vencida':       is_vistoria_vencida(v.data_validade, date.today()) if v.data_validade else False,
    }), 201


@app.route('/api/agencias/<int:agencia_id>/vistoria/upload', methods=['POST'])
@gestao_required
def api_vistoria_upload(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    v = ag.vistoria_bombeiros
    if not v:
        return jsonify({'erro': 'Cadastre a vistoria antes de fazer upload do PDF'}), 400

    if 'arquivo' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400

    arquivo = request.files['arquivo']
    if not arquivo.filename:
        return jsonify({'erro': 'Nenhum arquivo selecionado'}), 400

    nome_seguro = secure_filename(arquivo.filename)
    if not nome_seguro.lower().endswith('.pdf'):
        return jsonify({'erro': 'Apenas arquivos PDF são aceitos.'}), 400

    conteudo = arquivo.read()
    tamanho = len(conteudo)
    if tamanho > 20 * 1024 * 1024:
        return jsonify({'erro': 'O arquivo excede o limite de 20 MB.'}), 400

    if v.nome_arquivo:
        caminho_antigo = os.path.join(app.config['UPLOAD_FOLDER'], 'bombeiros', str(agencia_id), v.nome_arquivo)
        if os.path.exists(caminho_antigo):
            os.remove(caminho_antigo)

    nome_uuid = f"{uuid.uuid4().hex}_{nome_seguro}"
    pasta = os.path.join(app.config['UPLOAD_FOLDER'], 'bombeiros', str(agencia_id))
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, nome_uuid)
    with open(caminho, 'wb') as f:
        f.write(conteudo)

    v.nome_arquivo = nome_uuid
    v.nome_original = arquivo.filename
    v.atualizado_em = datetime.utcnow()
    db.session.commit()

    return jsonify({'ok': True, 'nome_original': v.nome_original}), 200


@app.route('/api/agencias/<int:agencia_id>/vistoria/download', methods=['GET'])
@login_required
def api_vistoria_download(agencia_id):
    ag = Agencia.query.get_or_404(agencia_id)
    v = ag.vistoria_bombeiros
    if not v or not v.nome_arquivo:
        return jsonify({'erro': 'Nenhum PDF de vistoria cadastrado'}), 404
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], 'bombeiros', str(agencia_id), v.nome_arquivo)
    if not os.path.exists(caminho):
        return jsonify({'erro': 'Arquivo não encontrado no servidor'}), 404
    return send_file(
        caminho,
        as_attachment=True,
        download_name=v.nome_original,
    )


@app.route('/api/config/limiar-idi', methods=['GET'])
@login_required
def api_config_limiar_idi_get():
    config = ConfiguracaoSistema.query.filter_by(chave='limiar_idi').first()
    limiar = float(config.valor) if config else 3.0
    return jsonify({'limiar_idi': limiar})


@app.route('/api/config/zonas-bioclimaticas', methods=['GET'])
@login_required
def api_zonas_bioclimaticas():
    """Retorna a lista de zonas bioclimáticas com descrição e consumo de referência."""
    zonas = [
        {'zona': k, 'descricao': v['descricao'], 'consumo_ref': v['consumo_ref']}
        for k, v in ZONAS_BIOCLIMATICAS.items()
    ]
    return jsonify(zonas)


@app.route('/api/config/limiar-idi', methods=['PUT'])
@gestao_required
def api_config_limiar_idi_put():
    data = request.get_json(force=True)
    if not data or 'limiar' not in data:
        return jsonify({'erro': 'Campo limiar é obrigatório'}), 400

    try:
        limiar = float(data['limiar'])
    except (TypeError, ValueError):
        return jsonify({'erro': 'O limiar deve ser um número'}), 400

    if not (0.1 <= limiar <= 5.0):
        return jsonify({'erro': 'O limiar deve estar entre 0,1 e 5,0.'}), 400

    config = ConfiguracaoSistema.query.filter_by(chave='limiar_idi').first()
    if config:
        config.valor = str(limiar)
    else:
        config = ConfiguracaoSistema(chave='limiar_idi', valor=str(limiar))
        db.session.add(config)
    db.session.commit()
    return jsonify({'limiar_idi': limiar})


@app.route('/api/usuarios')
@gestao_required
def api_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return jsonify([u.to_dict() for u in usuarios])


@app.route('/api/usuarios', methods=['POST'])
@gestao_required
def api_usuarios_criar():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    username = str(data.get('username', '')).strip()
    nome     = str(data.get('nome', '')).strip()
    email    = str(data.get('email', '')).strip()
    senha    = str(data.get('senha', '')).strip()
    nivel    = str(data.get('nivel', 'Consulta')).strip()

    if not all([username, nome, email, senha]):
        return jsonify({'erro': 'Username, nome, e-mail e senha são obrigatórios'}), 400

    if Usuario.query.filter_by(username=username).first():
        return jsonify({'erro': f'Username "{username}" já existe'}), 409
    if Usuario.query.filter_by(email=email).first():
        return jsonify({'erro': f'E-mail "{email}" já cadastrado'}), 409

    u = Usuario(username=username, nome=nome, email=email, nivel=nivel, ativo=True)
    u.set_senha(senha)
    db.session.add(u)
    db.session.commit()

    # Envia e-mail com as credenciais de acesso
    email_boas_vindas(u, senha)

    return jsonify(u.to_dict()), 201


@app.route('/api/usuarios/<int:usuario_id>', methods=['PUT'])
@gestao_required
def api_usuarios_editar(usuario_id):
    u    = Usuario.query.get_or_404(usuario_id)
    data = request.get_json(force=True)
    if not data:
        return jsonify({'erro': 'Dados inválidos'}), 400

    if 'nome' in data:
        u.nome = str(data['nome']).strip()
    if 'email' in data:
        email = str(data['email']).strip()
        existente = Usuario.query.filter_by(email=email).first()
        if existente and existente.id != u.id:
            return jsonify({'erro': 'E-mail já em uso'}), 409
        u.email = email
    if 'nivel' in data:
        u.nivel = str(data['nivel']).strip()
    if 'ativo' in data:
        u.ativo = bool(data['ativo'])
    if 'senha' in data and data['senha']:
        u.set_senha(str(data['senha']))

    db.session.commit()
    return jsonify(u.to_dict())


@app.route('/api/usuarios/<int:usuario_id>', methods=['DELETE'])
@gestao_required
def api_usuarios_deletar(usuario_id):
    u = Usuario.query.get_or_404(usuario_id)
    if u.id == session.get('user_id'):
        return jsonify({'erro': 'Você não pode excluir sua própria conta'}), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify({'ok': True})


# ── Solicitação de acesso ──────────────────────────────────────────────────────

@app.route('/solicitar-acesso', methods=['GET', 'POST'])
def solicitar_acesso():
    if request.method == 'POST':
        nome          = request.form.get('nome', '').strip()
        email         = request.form.get('email', '').strip().lower()
        justificativa = request.form.get('justificativa', '').strip()

        if not nome or not email:
            return render_template('solicitar_acesso.html', erro='Nome e e-mail são obrigatórios.')

        # Bloqueia se já existe usuário ativo com esse e-mail
        if Usuario.query.filter_by(email=email, ativo=True).first():
            return render_template('solicitar_acesso.html',
                                   erro='Este e-mail já possui acesso ao sistema.')

        # Bloqueia solicitação pendente duplicada
        pendente = SolicitacaoAcesso.query.filter_by(email=email, status='pendente').first()
        if pendente:
            return render_template('solicitar_acesso.html',
                                   erro='Já existe uma solicitação pendente para este e-mail.')

        sol = SolicitacaoAcesso(nome=nome, email=email, justificativa=justificativa)
        db.session.add(sol)
        db.session.commit()

        email_solicitacao_admin(sol)

        return render_template('solicitar_acesso.html', sucesso=True)

    return render_template('solicitar_acesso.html')


@app.route('/definir-senha/<token>', methods=['GET', 'POST'])
def definir_senha(token):
    sol = SolicitacaoAcesso.query.filter_by(token=token, status='aprovado').first()

    if not sol:
        return render_template('definir_senha.html', erro='Link inválido ou já utilizado.')

    if sol.token_expira and datetime.utcnow() > sol.token_expira:
        return render_template('definir_senha.html', erro='Este link expirou. Solicite um novo acesso.')

    if request.method == 'POST':
        senha   = request.form.get('senha', '')
        confirma = request.form.get('confirma', '')

        if len(senha) < 6:
            return render_template('definir_senha.html', token=token,
                                   erro='A senha deve ter pelo menos 6 caracteres.')
        if senha != confirma:
            return render_template('definir_senha.html', token=token,
                                   erro='As senhas não coincidem.')

        # Cria o usuário
        username = sol.email.split('@')[0].replace('.', '_').lower()
        # Garante username único
        base = username
        contador = 1
        while Usuario.query.filter_by(username=username).first():
            username = f"{base}{contador}"
            contador += 1

        u = Usuario(username=username, nome=sol.nome, email=sol.email,
                    nivel='Consulta', ativo=True)
        u.set_senha(senha)
        db.session.add(u)

        # Invalida o token
        sol.token = None
        sol.token_expira = None
        db.session.commit()

        return render_template('definir_senha.html', concluido=True, username=username)

    return render_template('definir_senha.html', token=token, nome=sol.nome)


# ── APIs de solicitações (admin) ───────────────────────────────────────────────

@app.route('/api/solicitacoes')
@gestao_required
def api_solicitacoes_listar():
    status = request.args.get('status', '')
    query  = SolicitacaoAcesso.query
    if status:
        query = query.filter_by(status=status)
    sols = query.order_by(SolicitacaoAcesso.criado_em.desc()).all()
    return jsonify([s.to_dict() for s in sols])


@app.route('/api/solicitacoes/<int:sol_id>/aprovar', methods=['POST'])
@gestao_required
def api_solicitacao_aprovar(sol_id):
    sol = SolicitacaoAcesso.query.get_or_404(sol_id)

    if sol.status != 'pendente':
        return jsonify({'erro': 'Solicitação já foi processada.'}), 400

    # Gera token seguro
    token = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
    sol.status       = 'aprovado'
    sol.token        = token
    sol.token_expira = datetime.utcnow() + timedelta(hours=24)
    sol.resolvido_em = datetime.utcnow()
    db.session.commit()

    link         = f"{_base_url()}/definir-senha/{token}"
    email_ok     = email_aprovacao(sol, link)

    return jsonify({'ok': True, 'link': link, 'email_enviado': email_ok})


@app.route('/api/solicitacoes/<int:sol_id>/rejeitar', methods=['POST'])
@gestao_required
def api_solicitacao_rejeitar(sol_id):
    sol = SolicitacaoAcesso.query.get_or_404(sol_id)

    if sol.status != 'pendente':
        return jsonify({'erro': 'Solicitação já foi processada.'}), 400

    sol.status       = 'rejeitado'
    sol.resolvido_em = datetime.utcnow()
    db.session.commit()

    email_rejeicao(sol)

    return jsonify({'ok': True})


@app.route('/api/solicitacoes/<int:sol_id>/reenviar', methods=['POST'])
@gestao_required
def api_solicitacao_reenviar(sol_id):
    """Gera novo token e reenvia o e-mail de aprovação (útil quando o link expirou)."""
    sol = SolicitacaoAcesso.query.get_or_404(sol_id)

    if sol.status not in ('aprovado',):
        return jsonify({'erro': 'Só é possível reenviar para solicitações aprovadas.'}), 400

    # Gera novo token
    token = uuid.uuid4().hex + uuid.uuid4().hex
    sol.token        = token
    sol.token_expira = datetime.utcnow() + timedelta(hours=24)
    db.session.commit()

    link         = f"{_base_url()}/definir-senha/{token}"
    email_ok     = email_aprovacao(sol, link)

    return jsonify({'ok': True, 'link': link, 'email_enviado': email_ok})


# ── Recuperação de senha ───────────────────────────────────────────────────────

@app.route('/recuperar-senha', methods=['GET', 'POST'])
def recuperar_senha():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        usuario = Usuario.query.filter(
            db.func.lower(Usuario.email) == email
        ).first()

        # Sempre exibe a mesma mensagem para não revelar se o e-mail existe
        mensagem = 'Se este e-mail estiver cadastrado, você receberá um link em instantes.'

        if usuario and usuario.ativo:
            token = uuid.uuid4().hex + uuid.uuid4().hex
            usuario.reset_token        = token
            usuario.reset_token_expira = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()

            link = f"{_base_url()}/redefinir-senha/{token}"
            email_recuperacao_senha(usuario, link)

        return render_template('recuperar_senha.html', enviado=True, mensagem=mensagem)

    return render_template('recuperar_senha.html')


@app.route('/redefinir-senha/<token>', methods=['GET', 'POST'])
def redefinir_senha(token):
    usuario = Usuario.query.filter_by(reset_token=token).first()

    if not usuario:
        return render_template('recuperar_senha.html',
                               erro='Link inválido ou já utilizado.')

    if usuario.reset_token_expira and datetime.utcnow() > usuario.reset_token_expira:
        usuario.reset_token        = None
        usuario.reset_token_expira = None
        db.session.commit()
        return render_template('recuperar_senha.html',
                               erro='Este link expirou. Solicite uma nova recuperação de senha.')

    if request.method == 'POST':
        senha    = request.form.get('senha', '')
        confirma = request.form.get('confirma', '')

        if len(senha) < 6:
            return render_template('redefinir_senha.html', token=token,
                                   erro='A senha deve ter pelo menos 6 caracteres.')
        if senha != confirma:
            return render_template('redefinir_senha.html', token=token,
                                   erro='As senhas não coincidem.')

        usuario.set_senha(senha)
        usuario.reset_token        = None
        usuario.reset_token_expira = None
        db.session.commit()

        return render_template('redefinir_senha.html', concluido=True)

    return render_template('redefinir_senha.html', token=token, nome=usuario.nome)


@app.errorhandler(403)
def forbidden(e):
    ctx = get_template_context()
    return render_template('errors/403.html', **ctx), 403


@app.errorhandler(404)
def not_found(e):
    ctx = get_template_context()
    return render_template('errors/404.html', **ctx), 404


@app.errorhandler(500)
def server_error(e):
    ctx = get_template_context()
    return render_template('errors/500.html', **ctx), 500


with app.app_context():
    db.create_all()
    seed_db()

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode)
