"""
Script para atualizar o campo IDI das agências no banco de dados
a partir do arquivo CSV do Archibus (RVP 2026-01-V2).

Estratégia de matching:
  1. Normaliza os nomes (remove acentos, maiúsculas, espaços extras)
  2. Tenta match exato normalizado
  3. Tenta match por substring (nome do banco contido no CSV ou vice-versa)
  4. Registra o que foi atualizado e o que não encontrou correspondência
"""

import sqlite3
import unicodedata
import re
import sys

CSV_FILE = "RVP - Archibus 2026-01-V2 - Tabela Vis-o Im-vel.csv"
DB_FILE  = "disec.db"


def normalizar(texto):
    """Remove acentos, converte para maiúsculas e colapsa espaços."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def ler_csv(caminho):
    """
    Lê o CSV (separado por TAB, encoding latin-1) e retorna lista de dicts
    com chaves: nome_construcao, nome_uor, idi
    Ignora linhas sem IDI válido.
    """
    registros = []
    try:
        with open(caminho, encoding="latin-1") as f:
            linhas = f.readlines()
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{caminho}' não encontrado.")
        sys.exit(1)

    if not linhas:
        print("ERRO: Arquivo CSV vazio.")
        sys.exit(1)

    # Cabeçalho na primeira linha
    cabecalho = [c.strip() for c in linhas[0].split("\t")]
    # Localiza índices das colunas relevantes
    try:
        idx_nome = cabecalho.index("Nome do construção")
    except ValueError:
        # Tenta variação sem acento
        idx_nome = next(
            (i for i, c in enumerate(cabecalho) if normalizar(c) == "NOME DO CONSTRUCAO"),
            None,
        )
    try:
        idx_idi = cabecalho.index("IDI")
    except ValueError:
        idx_idi = next(
            (i for i, c in enumerate(cabecalho) if normalizar(c) == "IDI"),
            None,
        )

    if idx_nome is None or idx_idi is None:
        print(f"ERRO: Colunas esperadas não encontradas. Cabeçalho: {cabecalho[:6]}")
        sys.exit(1)

    for linha in linhas[1:]:
        cols = linha.split("\t")
        if len(cols) <= max(idx_nome, idx_idi):
            continue
        nome = cols[idx_nome].strip()
        idi_str = cols[idx_idi].strip().replace(",", ".")
        if not nome or not idi_str:
            continue
        try:
            idi_val = float(idi_str)
        except ValueError:
            continue
        if not (1.0 <= idi_val <= 5.0):
            continue
        registros.append({"nome": nome, "nome_norm": normalizar(nome), "idi": idi_val})

    return registros
