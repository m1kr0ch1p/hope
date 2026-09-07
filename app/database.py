from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import DB_PATH, ensure_directories


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS coletas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    iniciada_em TEXT NOT NULL,
    finalizada_em TEXT,
    status TEXT NOT NULL,
    ordenacao TEXT NOT NULL,
    pagina_inicial INTEGER NOT NULL,
    paginas_lidas INTEGER NOT NULL DEFAULT 0,
    registros_lidos INTEGER NOT NULL DEFAULT 0,
    erro TEXT
);

CREATE TABLE IF NOT EXISTS casos (
    cnpd_id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    idade_atual INTEGER,
    idade_desaparecimento INTEGER,
    sexo TEXT,
    raca_cor TEXT,
    local_registro TEXT,
    uf_registro TEXT,
    data_desaparecimento TEXT,
    data_registro_desaparecimento TEXT,
    localizacao_confirmada TEXT,
    imagem_metadata_url TEXT,
    dados_fonte_json TEXT NOT NULL,
    hash_fonte TEXT NOT NULL,
    primeira_coleta_em TEXT NOT NULL,
    ultima_coleta_em TEXT NOT NULL,
    status_fonte TEXT NOT NULL DEFAULT 'ATIVO_NA_FONTE',
    ausencias_consecutivas INTEGER NOT NULL DEFAULT 0,
    status_investigacao TEXT NOT NULL DEFAULT 'NAO_INICIADA',
    prioridade TEXT NOT NULL DEFAULT 'NORMAL'
);

CREATE TABLE IF NOT EXISTS casos_coleta (
    coleta_id INTEGER NOT NULL,
    cnpd_id INTEGER NOT NULL,
    encontrado INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (coleta_id, cnpd_id),
    FOREIGN KEY (coleta_id) REFERENCES coletas(id) ON DELETE CASCADE,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS midias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    origem TEXT NOT NULL,
    nome_original TEXT,
    caminho_relativo TEXT,
    mime_type TEXT,
    tamanho_bytes INTEGER,
    url_origem TEXT,
    sha256 TEXT,
    descricao TEXT,
    conteudo_base64 TEXT,
    criado_em TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    titulo TEXT,
    valor TEXT NOT NULL,
    descricao TEXT,
    url_fonte TEXT,
    data_evento TEXT,
    classificacao TEXT NOT NULL DEFAULT 'DADO_BRUTO',
    nivel_confianca TEXT NOT NULL DEFAULT 'NAO_AVALIADO',
    status_verificacao TEXT NOT NULL DEFAULT 'PENDENTE',
    criado_por TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pessoas_relacionadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    nome TEXT NOT NULL,
    tipo_relacao TEXT,
    descricao_relacao TEXT,
    email TEXT,
    telefone TEXT,
    localidade TEXT,
    fonte_url TEXT,
    nivel_confianca TEXT NOT NULL DEFAULT 'NAO_AVALIADO',
    status_verificacao TEXT NOT NULL DEFAULT 'PENDENTE',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contas_sociais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    pessoa_relacionada_id INTEGER,
    plataforma TEXT NOT NULL,
    username TEXT,
    perfil_url TEXT,
    perfil_id TEXT,
    nome_exibicao TEXT,
    observacao TEXT,
    fonte_url TEXT,
    nivel_confianca TEXT NOT NULL DEFAULT 'NAO_AVALIADO',
    status_verificacao TEXT NOT NULL DEFAULT 'PENDENTE',
    criado_em TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE,
    FOREIGN KEY (pessoa_relacionada_id) REFERENCES pessoas_relacionadas(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pontos_geograficos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    titulo TEXT NOT NULL,
    descricao TEXT,
    tipo_local TEXT NOT NULL DEFAULT 'OUTRO',
    precisao_metros REAL,
    data_evento TEXT,
    fonte_url TEXT,
    nivel_confianca TEXT NOT NULL DEFAULT 'NAO_AVALIADO',
    status_verificacao TEXT NOT NULL DEFAULT 'PENDENTE',
    criado_em TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE,
    CHECK (latitude BETWEEN -90 AND 90),
    CHECK (longitude BETWEEN -180 AND 180)
);

CREATE TABLE IF NOT EXISTS anotacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    categoria TEXT NOT NULL DEFAULT 'ANOTACAO',
    conteudo TEXT NOT NULL,
    classificacao TEXT NOT NULL DEFAULT 'HIPOTESE',
    nivel_confianca TEXT NOT NULL DEFAULT 'NAO_AVALIADO',
    criado_por TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relatorios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    caminho_relativo TEXT,
    sha256 TEXT,
    modelo_ia TEXT,
    status TEXT NOT NULL DEFAULT 'GERADO',
    criado_em TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rascunhos_ia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,

    modelo TEXT NOT NULL,
    prompt_contexto_json TEXT NOT NULL,
    resposta_json TEXT NOT NULL,
    metricas_json TEXT,

    status TEXT NOT NULL DEFAULT 'RASCUNHO',
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,

    FOREIGN KEY (cnpd_id)
        REFERENCES casos(cnpd_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rascunhos_ia_caso ON rascunhos_ia(cnpd_id);
CREATE INDEX IF NOT EXISTS idx_evidencias_caso ON evidencias(cnpd_id);
CREATE INDEX IF NOT EXISTS idx_pessoas_caso ON pessoas_relacionadas(cnpd_id);
CREATE INDEX IF NOT EXISTS idx_sociais_caso ON contas_sociais(cnpd_id);
CREATE INDEX IF NOT EXISTS idx_pontos_caso ON pontos_geograficos(cnpd_id);
CREATE INDEX IF NOT EXISTS idx_anotacoes_caso ON anotacoes(cnpd_id);
CREATE INDEX IF NOT EXISTS idx_midias_caso ON midias(cnpd_id);
"""


def connect() -> sqlite3.Connection:
    ensure_directories()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)
