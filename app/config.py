"""
Configurações da aplicação HOPE — CNPD-OSINT.

Este módulo define constantes de configuração, URLs e caminhos de arquivos
utilizados pela aplicação para sincronização de dados do CNPD (Conselho Nacional
de justiça - Portal de Desaparecidos) e geração de relatórios OSINT.

Variáveis de ambiente:
    - Nenhuma: todas as configurações são definidas inline.

Uso:
    from app.config import BASE_DIR, DB_PATH, ensure_directories
"""

# Diretório base do projeto (pasta raiz)
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Diretórios de dados para armazenamento estruturado
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "cnpd"

# Diretórios de imagens: fonts de imagem CNPD e uploads do investigador
IMAGE_SOURCE_DIR = DATA_DIR / "images" / "source"
UPLOADS_DIR = DATA_DIR / "images" / "uploads"

# Diretórios para relatórios e exportações
REPORTS_DIR = DATA_DIR / "reports"
EXPORT_DIR = DATA_DIR / "exports"

# Diretório de logs da aplicação
LOG_DIR = BASE_DIR / "logs"

# Caminho do banco de dados SQLite
DB_PATH = DATA_DIR / "cnpd.db"

# URLs base do CNPD (Portal Público de Desaparecidos)
CNPD_BASE_URL = "https://cnpd.mj.gov.br"
CNPD_PAINEL_URL = f"{CNPD_BASE_URL}/painel-publico"

# URLs para serviço Ollama (LLM local)
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

# Configurações do modelo Ollama para geração de relatórios
OLLAMA_MODEL = "qwen3.5:latest"
OLLAMA_TIMEOUT_SECONDS = 300

# Parâmetros de geração: temperatura baixa para respostas determinísticas
OLLAMA_TEMPERATURE = 0.1
OLLAMA_NUM_PREDICT = 3000

# URLs API do CNPD para filtragem de casos
CNPD_FILTER_URL = (
    f"{CNPD_BASE_URL}/api/api/painel-publico/"
    "desaparecidos/filtrar"
)

# Template URL para metadados de imagem de desaparecimento
CNPD_IMAGE_METADATA_URL_TEMPLATE = (
    f"{CNPD_BASE_URL}/api/desaparecimentos/"
    "{desaparecimento_id}/arquivos-imagem/main"
)

# Configurações padrão para operações
DEFAULT_ORDER = "MAIS_RECENTE"
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_PAGE_DELAY_SECONDS = 1.0
DEFAULT_IMAGE_DELAY_SECONDS = 0.5

# Limite máximo para upload de arquivos (10 MB)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def ensure_directories() -> None:
    """
    Cria os diretórios usados pela aplicação caso ainda não existam.

    Essencial para inicialização da aplicação, garantindo que todos os
    diretórios necessários para dados, imagens, logs e relatórios estejam
    disponíveis antes de qualquer operação de leitura/escrita.

    Raises:
        OSError: Se não for possível criar diretórios (problemas de permissão).
    """
    directories = (
        DATA_DIR,
        RAW_DIR,
        IMAGE_SOURCE_DIR,
        UPLOADS_DIR,
        REPORTS_DIR,
        EXPORT_DIR,
        LOG_DIR,
    )

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
