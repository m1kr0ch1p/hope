"""
Módulo de acesso ao banco de dados SQLite.

Este módulo fornece funções e esquemas para acesso, criação e gerenciamento
do banco de dados SQLite usado pela aplicação HOPE — CNPD-OSINT. O banco
armazena casos de desaparecidos, mídias, evidências, anotações e dados de
investigação.

Uso:
    from app.database import get_connection, initialize_database
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from app.config import DB_PATH, ensure_directories

# Schema SQL completo com todas as tabelas necessárias
# Inclui chaves estrangeiras para integridade referencial
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

CREATE TABLE IF NOT EXISTS grafos_conexoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL,
    gerado_em TEXT NOT NULL,
    modelo_ia TEXT NOT NULL,
    gerado_por TEXT NOT NULL DEFAULT 'IA_LOCAL',
    status TEXT NOT NULL DEFAULT 'RASCUNHO',
    prompt_contexto_json TEXT,
    resposta_json TEXT NOT NULL,
    metros_json TEXT,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS grafos_nós (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grafo_id INTEGER NOT NULL,
    origem TEXT NOT NULL DEFAULT 'IA',
    tipo_nó TEXT NOT NULL,
    grupo_nó TEXT,
    rótulo TEXT NOT NULL,
    subtítulo TEXT,
    valor_principal TEXT,
    dados_extras_json TEXT,
    nível_confianca TEXT NOT NULL DEFAULT 'IA_SUGERIDO',
    FOREIGN KEY (grafo_id) REFERENCES grafos_conexoes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS grafos_arestas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grafo_id INTEGER NOT NULL,
    nó_origem INTEGER NOT NULL,
    nó_destino INTEGER NOT NULL,
    tipo_relação TEXT NOT NULL,
    rótulo_aresta TEXT,
    origem_aresta TEXT NOT NULL DEFAULT 'IA',
    nível_confianca TEXT NOT NULL DEFAULT 'IA_SUGERIDO',
    observação TEXT,
    FOREIGN KEY (grafo_id) REFERENCES grafos_conexoes(id) ON DELETE CASCADE,
    FOREIGN KEY (nó_origem) REFERENCES grafos_nós(id) ON DELETE CASCADE,
    FOREIGN KEY (nó_destino) REFERENCES grafos_nós(id) ON DELETE CASCADE,
    CHECK (nó_origem != nó_destino)
);

CREATE INDEX IF NOT EXISTS idx_grafos_caso ON grafos_conexoes(cnpd_id);
CREATE INDEX IF NOT EXISTS idx_nós_grafo ON grafos_nós(grafo_id);
CREATE INDEX IF NOT EXISTS idx_arestas_grafo ON grafos_arestas(grafo_id);

CREATE TABLE IF NOT EXISTS grafos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpd_id INTEGER NOT NULL UNIQUE,
    nome_desaparecido TEXT NOT NULL,
    gerado_em TEXT NOT NULL,
    modelo_usado TEXT NOT NULL,
    FOREIGN KEY (cnpd_id) REFERENCES casos(cnpd_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS grafo_nos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grafo_id INTEGER NOT NULL,
    tipo_nó TEXT NOT NULL,
    rotulo TEXT NOT NULL,
    dados_json TEXT,
    nivel_confianca TEXT DEFAULT 'IA_SUGERIDO',
    external_id TEXT,
    FOREIGN KEY (grafo_id) REFERENCES grafos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS grafo_arestas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grafo_id INTEGER NOT NULL,
    nó_origem INTEGER NOT NULL,
    nó_destino INTEGER NOT NULL,
    tipo_relacionamento TEXT NOT NULL,
    descricao TEXT,
    sapiens_origem TEXT NOT NULL DEFAULT 'IA',
    FOREIGN KEY (grafo_id) REFERENCES grafos(id) ON DELETE CASCADE,
    FOREIGN KEY (nó_origem) REFERENCES grafo_nos(id) ON DELETE CASCADE,
    FOREIGN KEY (nó_destino) REFERENCES grafo_nos(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_grafo_nos ON grafo_nos(grafo_id);
CREATE INDEX IF NOT EXISTS idx_grafo_arestas ON grafo_arestas(grafo_id);

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
CREATE INDEX IF NOT EXISTS idx_grafos_caso ON grafos_conexoes(cnpd_id);
"""


def connect() -> sqlite3.Connection:
    """
    Cria e retorna uma conexão SQLite configurada para a aplicação.

    Configura a conexão com:
    - Row factory para acesso por nome de coluna
    - Foreign keys habilitados
    - Modo WAL (Write-Ahead Logging) para melhor performance concorrente

    Returns:
        sqlite3.Connection: Conexão configurada ao banco de dados.
    """
    ensure_directories()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Gerenciador de contexto para conexão SQLite com transação automática.

    Garantia atomicidade:
    - Commit automático ao sair com sucesso
    - Rollback automático em caso de exceção
    - Fechamento da conexão em todos os casos

    Yields:
        sqlite3.Connection: Conexão SQLite para uso dentro do contexto.

    Raises:
        Exception: Qualquer exceção é propagada após rollback.
    """
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
    """
    Inicializa o banco de dados executando o schema completo.

    Cria todas as tabelas definidas no SCHEMA, incluindo índices.
    É idempotente - pode ser chamado múltiplas vezes sem erro.
    Também garante que colunas introduzidas por atualizações existam.
    """
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        _migrate_columns(conn)


def _migrate_columns(conn: sqlite3.Connection) -> None:
    """Garante que colunas introduzidas por atualizações estejam presentes."""
    def column_exists(table: str, column: str) -> bool:
        for r in conn.execute(f"PRAGMA table_info({table})"):
            if r["name"] == column:
                return True
        return False

    if not column_exists("grafos_nós", "id_ia"):
        conn.execute("ALTER TABLE grafos_nós ADD COLUMN id_ia TEXT")