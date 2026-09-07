from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw" / "cnpd"
IMAGE_SOURCE_DIR = DATA_DIR / "images" / "source"
EXPORT_DIR = DATA_DIR / "exports"
LOG_DIR = BASE_DIR / "logs"

DB_PATH = DATA_DIR / "cnpd.db"

CNPD_BASE_URL = "https://cnpd.mj.gov.br"
CNPD_PAINEL_URL = f"{CNPD_BASE_URL}/painel-publico"
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


def ensure_directories() -> None:
    for directory in (
        DATA_DIR,
        RAW_DIR,
        IMAGE_SOURCE_DIR,
        EXPORT_DIR,
        LOG_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
