# HOPE

MVP local para sincronizar registros públicos do painel CNPD em SQLite e visualizá-los em um dashboard FastAPI.

## Requisitos

- Python 3.11 ou superior
- Acesso de rede ao painel público CNPD

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -r requirements.txt
python run.py
```

Abra `http://127.0.0.1:8000`.

## Primeiro uso

1. Acesse `http://127.0.0.1:8000/sincronizar`.
2. Use `Página inicial = 0`, `Máximo de páginas = 3`.
3. Opcionalmente marque o download de imagens oficiais.
4. Aguarde a execução em segundo plano e atualize a página de sincronização.
5. Abra `http://127.0.0.1:8000/` para consultar os casos inseridos no SQLite.

## Dados locais

- Banco: `data/cnpd.db`
- JSON bruto por coleta: `data/raw/cnpd/coleta_{id}/`
- Imagens oficiais: `data/images/source/{cnpd_id}/`
- Logs/erros do servidor: console do Uvicorn

## Limites operacionais

- O coletor usa o endpoint público validado e inclui atraso entre páginas.
- Não execute múltiplas sincronizações paralelas.
- Uma ausência em uma coleta não confirma localização, óbito ou resolução de caso.
- Esta versão ainda não possui autenticação; use apenas em ambiente local controlado.
