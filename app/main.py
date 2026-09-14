"""
Aplicação FastAPI principal HOPE — CNPD-OSINT.

Este módulo configura e inicializa a aplicação FastAPI, incluindo:
- Configuração do logging
- Rotas de API para casos, sincronização, relatórios e IA
- Servir arquivos estáticos (CSS, JS, imagens)
- Gerenciamento do ciclo de vida (inicialização do banco)

Uso:
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, DB_PATH, ensure_directories
from app.database import initialize_database
from app.routers import ai, cases, reports, sync, graph

# Configuração global de logging da aplicação
logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Gerenciador de ciclo de vida da aplicação FastAPI.

    Executa tarefas de inicialização antes de iniciar o servidor:
    - Cria diretórios necessários
    - Inicializa o banco de dados SQLite

    Yields:
        None: Quando o gerenciador sai, a aplicação está pronta para receber requisições.
    """
    ensure_directories()
    initialize_database()

    logging.getLogger("hope").info(
        "Banco SQLite: %s",
        DB_PATH.resolve(),
    )

    yield


# Instância principal da aplicação FastAPI
app = FastAPI(
    title="HOPE — CNPD-OSINT",
    version="1.1.0",
    lifespan=lifespan,
)

# Monta diretório de arquivos estáticos
# Acesso via /static/<caminho>
app.mount(
    "/static",
    StaticFiles(
        directory=str(BASE_DIR / "app" / "static")
    ),
    name="static",
)

# Registra os routers (roteadores) da API
# Cada router agrupa endpoints funcionais
app.include_router(cases.router)
app.include_router(sync.router)
app.include_router(reports.router)
app.include_router(ai.router)
app.include_router(graph.router)