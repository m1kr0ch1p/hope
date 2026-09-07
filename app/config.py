from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "cnpd"

IMAGE_SOURCE_DIR = DATA_DIR / "images" / "source"
UPLOADS_DIR = DATA_DIR / "images" / "uploads"

REPORTS_DIR = DATA_DIR / "reports"
EXPORT_DIR = DATA_DIR / "exports"
LOG_DIR = BASE_DIR / "logs"

DB_PATH = DATA_DIR / "cnpd.db"

CNPD_BASE_URL = "https://cnpd.mj.gov.br"
CNPD_PAINEL_URL = f"{CNPD_BASE_URL}/painel-publico"

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

OLLAMA_MODEL = "qwen3.5:latest"
OLLAMA_TIMEOUT_SECONDS = 360

OLLAMA_TEMPERATURE = 0.1
OLLAMA_NUM_PREDICT = 7000

CNPD_FILTER_URL = (
    f"{CNPD_BASE_URL}/api/api/painel-publico/"
    "desaparecidos/filtrar"
)

CNPD_IMAGE_METADATA_URL_TEMPLATE = (
    f"{CNPD_BASE_URL}/api/desaparecimentos/"
    "{desaparecimento_id}/arquivos-imagem/main"
)

DEFAULT_ORDER = "MAIS_RECENTE"
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_PAGE_DELAY_SECONDS = 1.0
DEFAULT_IMAGE_DELAY_SECONDS = 0.5

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def ensure_directories() -> None:
    """Cria os diretórios usados pela aplicação caso ainda não existam."""
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
