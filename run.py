"""
Ponto de entrada para execução da aplicação via uvicorn.

Este script permite iniciar o servidor de desenvolvimento com recarregamento
automático (hot reload) para desenvolvimento.

Uso:
    python run.py
    # ou
    uvicorn run:app --reload
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )