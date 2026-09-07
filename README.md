# HOPE — CNPD-OSINT

O **HOPE** é uma aplicação local para auxiliar o gerenciamento de investigações OSINT relacionadas a pessoas desaparecidas. A ferramenta funciona como um agregador estruturado de dados: importa registros públicos do Cadastro Nacional de Pessoas Desaparecidas (CNPD), organiza evidências inseridas pelo investigador e oferece recursos para interpretação, análise, georreferenciamento, enriquecimento assistido por IA local e documentação dos casos.

A aplicação não substitui autoridades competentes, protocolos institucionais ou validação humana. Seu propósito é apoiar a organização do trabalho investigativo, preservar fontes e evidências, reduzir a dispersão de informações e facilitar a produção de rascunhos e relatórios revisáveis.

> **Uso responsável:** dados sobre pessoas desaparecidas são sensíveis. Use esta ferramenta somente em ambiente controlado, com finalidade legítima, observando a legislação aplicável, a privacidade e a segurança dos dados. O desaparecimento de um registro da fonte pública não comprova localização, óbito, encerramento ou resolução de um caso.

---

## Finalidade

Investigações sobre pessoas desaparecidas podem envolver registros públicos, pesquisas abertas na internet, consultas com operadores avançados, conteúdos de redes sociais, documentos, imagens, contatos, relatos e pontos geográficos. Essas informações tendem a ficar distribuídas, sem padronização e com diferentes graus de confiabilidade.

O HOPE centraliza esses elementos por caso para que o investigador possa:

- Manter os dados públicos de origem separados de dados e análises investigativas.
- Registrar fonte, data, contexto e nível de confiança de cada achado.
- Diferenciar dados brutos, fatos confirmados, hipóteses e pendências.
- Relacionar pessoas próximas, contas sociais, telefones, e-mails e URLs.
- Registrar e visualizar locais relevantes em um mapa.
- Preservar mídias e hashes SHA-256 para rastreabilidade básica.
- Gerar rascunhos analíticos estruturados usando IA local.
- Revisar o conteúdo antes de gerar relatórios PDF.

A aplicação foi pensada para execução local, utilizando FastAPI, SQLite, Leaflet, OpenStreetMap, ReportLab e Ollama.

---

## Funcionalidades

### Integração com CNPD

- Consulta ao Painel Público do Cadastro Nacional de Pessoas Desaparecidas.
- Coleta paginada por API.
- Preservação do JSON bruto de cada página processada.
- Normalização dos registros no banco SQLite.
- Identificação estável pelo campo `cnpd_id`.
- Histórico de coletas, páginas processadas, registros lidos e erros.
- Atualização de registros existentes sem duplicar casos.
- Download opcional de imagens oficiais disponíveis.

A integração observada utiliza:

```text
POST https://cnpd.mj.gov.br/api/api/painel-publico/desaparecidos/filtrar
```

Parâmetros de consulta:

```text
ordenacao=MAIS_RECENTE
pagina=N
```

Corpo JSON sem filtros:

```json
{}
```

A resposta possui a coleção:

```json
{
  "desaparecidos": []
}
```

### Dados oficiais armazenados

Quando presentes no retorno do CNPD, são armazenados:

- ID CNPD;
- Nome;
- Idade atual;
- Idade na data do desaparecimento;
- Sexo;
- Raça/cor;
- Local e UF de registro;
- Data do desaparecimento;
- Data do registro;
- Indicador de localização confirmada;
- Hash SHA-256 do objeto recebido da fonte;
- Data da primeira e da última coleta;
- JSON original retornado pela fonte;
- URL de metadados da imagem principal.

### Imagens oficiais do CNPD

O endpoint de imagem principal retorna metadados JSON. A imagem é disponibilizada em Base64 no campo:

```text
arquivoCnpd.arquivoDTO.conteudo
```

O HOPE pode:

- Consultar os metadados por ID CNPD;
- Extrair e decodificar a imagem Base64;
- Validar assinaturas de JPEG, PNG, GIF e WEBP;
- Salvar a mídia localmente;
- Calcular SHA-256;
- Registrar metadados no banco;
- Exibir a imagem no dashboard;
- Incluir imagens locais no relatório PDF.

### Dashboard de casos

- Listagem de casos sincronizados localmente.
- Busca por nome, ID CNPD ou localidade.
- Filtro por UF.
- Filtro por status da fonte.
- Dashboard individual por caso.
- Exibição dos dados oficiais e das imagens associadas.
- Histórico de sincronizações em que o caso apareceu.
- Formulários para evidências, pessoas, redes sociais, localização, mídias e anotações.

### Pesquisas abertas e evidências

O investigador pode registrar:

- Pesquisas abertas na internet;
- Consultas e Google Dorks;
- URLs;
- E-mails;
- Telefones;
- Usernames;
- IDs de contas;
- Perfis sociais;
- Notícias;
- Documentos;
- Observações;
- Dados livres e outros achados.

Cada evidência pode conter:

- Tipo;
- Título ou consulta;
- Valor principal;
- Descrição e contexto;
- URL da fonte;
- Data do evento;
- Classificação;
- Nível de confiança;
- Status de verificação;
- Datas de criação e atualização.

Classificações recomendadas:

```text
DADO_BRUTO
FATO_CONFIRMADO
HIPOTESE
PENDENCIA
```

> Um dado bruto é um registro ainda não validado. Uma hipótese é uma possibilidade analítica e não deve ser tratada como fato confirmado.

### Pessoas relacionadas

Permite registrar parentes, amigos, conhecidos ou outros vínculos relevantes:

- Nome;
- Tipo de relação;
- Descrição da relação;
- E-mail;
- Telefone;
- Localidade;
- URL/fonte;
- Nível de confiança;
- Status de verificação.

### Redes sociais

Permite registrar contas associadas ao desaparecido ou a pessoas relacionadas:

- Plataforma;
- Username;
- ID do perfil;
- URL do perfil;
- Nome de exibição;
- Observações;
- Fonte;
- Nível de confiança;
- Status de verificação.

### Upload de imagens

- Upload de imagens no dashboard do caso.
- Limite padrão de 10 MB por arquivo.
- Validação inicial de conteúdo de imagem.
- Salvamento do arquivo no diretório local.
- Conversão do arquivo para Base64.
- Armazenamento do Base64 associado ao caso na tabela `midias`.
- Cálculo de hash SHA-256.
- Registro de nome, MIME, tamanho, descrição e data.
- Galeria de imagens com rolagem interna.
- Inclusão de imagens no relatório PDF.

O arquivo é mantido também no sistema de arquivos para tornar visualização, backups e exportações mais eficientes.

### Localizações e mapa

- Cadastro manual de latitude e longitude.
- Título/flag descritiva do ponto.
- Tipo de local.
- Data do evento.
- URL/fonte.
- Descrição e nível de confiança.
- Mapa dinâmico com Leaflet.
- Camada cartográfica OpenStreetMap.
- Marcadores dos pontos associados ao caso.
- Zoom automático para um ou vários pontos.
- Mapa estático opcional no PDF.

Tipos de local disponíveis:

```text
ULTIMO_LOCAL_CONHECIDO
LOCAL_DESAPARECIMENTO
AVISTAMENTO
RESIDENCIA
OUTRO
```

### Anotações e análise

- Campo livre para informações adicionais.
- Registro de anotações analíticas.
- Categorias para fatos, hipóteses, pendências e próximos passos.
- Separação conceitual entre informação observada e interpretação.

Categorias sugeridas:

```text
ANOTACAO
FATO_CONFIRMADO
HIPOTESE
PENDENCIA
PROXIMO_PASSO
```

### Relatórios PDF

- Geração de relatório por caso.
- Abertura do PDF em nova aba do navegador.
- Salvamento em `data/reports/`.
- Hash SHA-256 do PDF.
- Registro na tabela `relatorios`.
- Inclusão de dados oficiais, evidências, pessoas relacionadas, redes sociais, pontos, anotações e mídias locais.
- Aviso de que o relatório requer revisão humana.

O PDF é um documento operacional: ele organiza informações disponíveis, mas não confirma automaticamente fatos ou hipóteses.

---

## Ollama e Qwen 3.5

O HOPE possui integração com Ollama local para gerar um **rascunho estruturado de enriquecimento analítico** a partir dos dados que já estão armazenados no caso.

O modelo configurado é:

```text
qwen3.5:latest
```

A integração foi validada no modo JSON e produz resposta final estruturada no campo `response` da API do Ollama. O uso de `format: "json"` é preferido neste projeto porque, no ambiente testado, o JSON Schema completo pode levar o modelo a consumir tokens no campo interno `thinking` e encerrar sem resposta final.

### Propósito da IA local

A IA local serve para:

- Organizar dados oficiais em formato narrativo e estruturado;
- Destacar evidências registradas no banco;
- Criar cronologia baseada nas informações existentes;
- Identificar lacunas informacionais;
- Listar pendências;
- Sugerir próximos passos legais, proporcionais e verificáveis;
- Produzir hipóteses apenas quando houver base explícita e sempre com limitações declaradas;
- Exibir alertas éticos relevantes.

A IA local **não deve**:

- Pesquisar a internet;
- Alterar o banco automaticamente;
- Fazer contato com pessoas, familiares ou contas sociais;
- Expor dados publicamente;
- Confirmar localização, identidade, óbito, crime ou vínculo sem dado explícito;
- Transformar dados brutos em fatos confirmados;
- Classificar ou interpretar imagens automaticamente;
- Tomar decisões investigativas sem revisão humana.

### Fluxo do rascunho IA

```text
Dados do caso no SQLite
        │
        ├── Dados oficiais CNPD
        ├── Evidências registradas
        ├── Pessoas relacionadas
        ├── Contas sociais
        ├── Pontos geográficos
        └── Anotações
        │
        ▼
Contexto compacto e sem Base64
        │
        ▼
Ollama + qwen3.5:latest
        │
        ▼
Rascunho JSON estruturado
        │
        ▼
Revisão humana
        │
        ▼
Relatório PDF operacional
```

O Base64 das imagens e o JSON bruto completo do CNPD não são enviados ao modelo. Imagens e mapa entram no PDF pelo serviço de relatório, sem necessidade de interpretação automática pelo LLM.

### Estrutura de resposta esperada

O rascunho é retornado em JSON com campos similares a:

```json
{
  "titulo": "",
  "resumo_executivo": "",
  "dados_oficiais": [],
  "evidencias_relevantes": [],
  "pessoas_e_vinculos": [],
  "cronologia": [],
  "hipoteses": [],
  "pendencias": [],
  "proximos_passos": [],
  "alertas_eticos": []
}
```

As hipóteses devem conter:

- Descrição;
- Base disponível;
- Limitação.

Isso ajuda a distinguir inferências de fatos.

### Regras aplicadas ao prompt

A aplicação instrui o modelo a:

- Usar exclusivamente os dados fornecidos;
- Não inventar nomes, locais, datas, vínculos, eventos, fontes ou conclusões;
- Não tratar `DADO_BRUTO` como `FATO_CONFIRMADO`;
- Registrar ausência de informação como pendência ou lista vazia;
- Rotular hipóteses explicitamente;
- Não afirmar localização, óbito, crime ou vínculo sem confirmação explícita;
- Não listar ou classificar imagens como evidências relevantes;
- Não gerar instruções de assédio, exposição, rastreamento invasivo ou violação de privacidade;
- Gerar apenas JSON válido para processamento local;
- Produzir texto no campo de resposta final, e não apenas no campo interno de raciocínio.

### Instalação do Ollama

Verifique se o Ollama está instalado:

```powershell
ollama --version
```

Baixe o modelo:

```powershell
ollama pull qwen3.5:latest
```

Teste o modelo:

```powershell
ollama run qwen3.5:latest
```

Envie uma mensagem curta:

```text
Responda somente: OK
```

Para sair:

```text
/bye
```

O Ollama disponibiliza uma API local, normalmente em:

```text
http://127.0.0.1:11434
```

O HOPE usa:

```text
POST http://127.0.0.1:11434/api/generate
```

Caso a API não esteja disponível, inicie o serviço:

```powershell
ollama serve
```

### Teste da API Ollama

No PowerShell:

```powershell
$body = @{
  model = "qwen3.5:latest"
  prompt = 'Retorne somente este JSON válido: {"ok":true}'
  stream = $false
  format = "json"
  think = $false
  options = @{
    temperature = 0
    num_predict = 500
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Uri "http://127.0.0.1:11434/api/generate" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

A resposta esperada contém:

```json
{
  "response": "{\"ok\":true}",
  "done": true,
  "done_reason": "stop"
}
```

### Configuração do Ollama

No arquivo `app/config.py`, mantenha ou adicione:

```python
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"

OLLAMA_MODEL = "qwen3.5:latest"
OLLAMA_TIMEOUT_SECONDS = 360

OLLAMA_TEMPERATURE = 0.1
OLLAMA_NUM_PREDICT = 7000
```

A temperatura baixa favorece previsibilidade. O orçamento de tokens deve ser suficiente para que o modelo produza a resposta JSON final, especialmente em variantes que exibem raciocínio interno.

### Gerar rascunho pelo dashboard

1. Abra um caso no dashboard.
2. Cadastre ou revise evidências, pessoas, contas, localizações e anotações.
3. Clique em **Gerar rascunho com IA**.
4. A aplicação envia apenas um contexto compactado para o Ollama local.
5. O rascunho é aberto em uma nova aba.
6. Revise o conteúdo integralmente.
7. Corrija, descarte ou complemente formulações inadequadas.
8. Gere o PDF apenas depois da revisão.

A saída é registrada na tabela:

```text
rascunhos_ia
```

São preservados:

- Caso associado;
- Modelo utilizado;
- Contexto compacto enviado ao modelo;
- Resposta JSON;
- Métricas de geração;
- Modo de geração;
- Status;
- Datas de criação e atualização.

### Teste do serviço de IA

Crie ou mantenha o arquivo `testar_ollama.py`:

```python
from __future__ import annotations

import json

from app.services.investigation_service import build_case_context
from app.services.ollama_service import generate_report_draft


CNPD_ID = 215477


def main() -> None:
    context = build_case_context(CNPD_ID)
    result = generate_report_draft(context)

    print("Modelo:", result["model"])
    print("Modo:", result["generation_mode"])
    print("Métricas:")
    print(json.dumps(result["metrics"], ensure_ascii=False, indent=2))
    print("Rascunho:")
    print(json.dumps(result["draft"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

Execute:

```powershell
python .\testar_ollama.py
```

Uma execução bem-sucedida deve apresentar:

```text
Modo: json_mode
...
"done_reason": "stop"
```

### Falhas comuns do Ollama

| Sintoma | Possível causa | Ação recomendada |
|---|---|---|
| `Connection refused` | Serviço Ollama não iniciado | Execute `ollama serve` |
| `model not found` | Modelo não foi baixado | Execute `ollama pull qwen3.5:latest` |
| `response` vazio e `done_reason: length` | Modelo consumiu tokens em `thinking` | Use `think: false`, `format: "json"`, prompt compacto e aumente `OLLAMA_NUM_PREDICT` |
| JSON inválido | Modelo adicionou texto fora do objeto | Mantenha `format: "json"` e valide com `json.loads` |
| Timeout | Modelo lento, pouca RAM/VRAM ou prompt grande | Aumente timeout, reduza contexto e verifique recursos locais |

---

## Arquitetura

```text
cnpd-osint/
├── README.md
├── requirements.txt
├── run.py
├── diagnostico.py
├── sincronizar_teste.py
├── testar_ollama.py
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── ai.py
│   │   ├── cases.py
│   │   ├── reports.py
│   │   └── sync.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cnpd_client.py
│   │   ├── investigation_service.py
│   │   ├── ollama_service.py
│   │   ├── report_service.py
│   │   └── sync_service.py
│   ├── templates/
│   │   ├── ai_draft.html
│   │   ├── base.html
│   │   ├── case_detail.html
│   │   ├── index.html
│   │   └── sync.html
│   └── static/
│       └── css/
│           └── app.css
├── data/
│   ├── cnpd.db
│   ├── raw/cnpd/
│   ├── images/source/
│   ├── images/uploads/
│   ├── reports/
│   └── exports/
└── logs/
```

---

## Requisitos

- Python 3.11 ou superior;
- FastAPI;
- Uvicorn;
- Jinja2;
- `python-multipart`;
- `requests`;
- ReportLab;
- SQLite, incluído na distribuição padrão do Python;
- Ollama instalado localmente para enriquecimento com IA;
- Modelo `qwen3.5:latest` baixado;
- Navegador moderno;
- Conexão de internet para CNPD, Leaflet e tiles do OpenStreetMap.

Para mapa estático no PDF, instale também as dependências definidas pelo serviço de relatório, como Pillow e biblioteca de mapa estático, se essa funcionalidade estiver habilitada na sua versão.

---

## Instalação

### Windows PowerShell

Abra o PowerShell na pasta do projeto:

```powershell
cd H:\3.Missing_person_project\cnpd-osint
```

Crie o ambiente virtual:

```powershell
python -m venv env
```

Ative-o:

```powershell
.\env\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r .\requirements.txt
```

Prepare o modelo local:

```powershell
ollama pull qwen3.5:latest
```

Inicie a aplicação:

```powershell
python .\run.py
```

Abra no navegador:

```text
http://127.0.0.1:8000
```

### Linux e macOS

```bash
cd cnpd-osint

python3 -m venv env
source env/bin/activate

pip install -r requirements.txt
ollama pull qwen3.5:latest
python run.py
```

Abra:

```text
http://127.0.0.1:8000
```

---

## Primeiro uso

1. Inicie o servidor:

   ```powershell
   python .\run.py
   ```

2. Abra a página de sincronização:

   ```text
   http://127.0.0.1:8000/sincronizar
   ```

3. Para o primeiro teste, configure:

   ```text
   Página inicial: 0
   Máximo de páginas: 1
   Ordenação: Mais recente
   Baixar imagens oficiais: desmarcado
   ```

4. Clique em **Iniciar sincronização**.

5. Abra a lista de casos:

   ```text
   http://127.0.0.1:8000/
   ```

6. Selecione um caso usando **Abrir**.

7. Registre evidências, pessoas relacionadas, contas sociais, coordenadas, imagens e anotações.

8. Opcionalmente, gere um rascunho com IA local.

9. Revise o rascunho e as informações do caso.

10. Gere o relatório PDF apenas após revisão humana.

---

## Banco de dados

O banco SQLite é criado em:

```text
data/cnpd.db
```

### Tabelas principais

| Tabela | Finalidade |
|---|---|
| `casos` | Dados normalizados do CNPD |
| `coletas` | Histórico de sincronizações |
| `casos_coleta` | Presença de um caso em uma coleta |
| `midias` | Imagens oficiais e uploads do investigador |
| `evidencias` | Pesquisas, URLs, e-mails, telefones e outros achados |
| `pessoas_relacionadas` | Pessoas próximas e vínculos registrados |
| `contas_sociais` | Perfis, usernames e IDs sociais |
| `pontos_geograficos` | Coordenadas e contexto espacial |
| `anotacoes` | Análises, fatos, hipóteses e pendências |
| `rascunhos_ia` | Contextos e respostas geradas pelo Ollama |
| `relatorios` | PDFs e hashes associados |

### Status de fonte

```text
ATIVO_NA_FONTE
AUSENTE_EM_UMA_COLETA
AUSENTE_EM_MULTIPLAS_COLETAS
PENDENTE_DE_REVISAO
ARQUIVADO_POR_CONFIRMACAO
```

A ausência em uma coleta deve ser tratada como evento operacional sujeito a revisão, nunca como conclusão automática sobre a pessoa.

---

## Armazenamento local

```text
data/cnpd.db
data/raw/cnpd/coleta_{id}/pagina_00000.json
data/images/source/{cnpd_id}/
data/images/uploads/{cnpd_id}/
data/reports/
data/exports/
```

---

## Diagnóstico

### Sincronização sem interface

```powershell
python .\sincronizar_teste.py
```

### Banco SQLite

```powershell
python .\diagnostico.py
```

### Integração Ollama

```powershell
python .\testar_ollama.py
```

### CSS

Abra no navegador:

```text
http://127.0.0.1:8000/static/css/app.css
```

Após alterar CSS ou templates, use `Ctrl+F5` para recarregar sem cache.

---

## Segurança, privacidade e ética

- Mantenha a aplicação em computador ou rede controlada.
- Não exponha as portas `8000` e `11434` diretamente na internet.
- Proteja o banco SQLite, as mídias, os rascunhos de IA e os backups.
- Não envie Base64 de imagens, JSON bruto integral ou dados desnecessários ao modelo.
- Diferencie visualmente dados brutos, fatos confirmados, hipóteses e pendências.
- Registre fonte, contexto e nível de confiança para cada evidência.
- Não automatize contato com familiares, terceiros ou perfis sociais.
- Não use reconhecimento facial ou associação automática de identidade sem base legal, governança e revisão humana especializada.
- Revise todo rascunho gerado pelo Ollama antes de aproveitá-lo em documento final.
- Faça backups regulares de `data/cnpd.db`, `data/images/` e `data/reports/`.
- Considere criptografia de disco, controle de acesso e políticas de retenção para uso continuado.

---

## Limitações atuais

- Não há autenticação ou controle de permissões por usuário;
- não há trilha completa de auditoria por investigador;
- edição e exclusão podem não estar disponíveis para todos os recursos;
- o mapa depende de Leaflet por CDN e de tiles OpenStreetMap;
- a geração de mapa estático depende das bibliotecas habilitadas e da disponibilidade de tiles;
- o modelo pode omitir dados, interpretar mal o contexto ou produzir formulações inadequadas;
- o rascunho IA não é uma conclusão investigativa;
- não há automação OSINT autônoma;
- não há confirmação automática de casos resolvidos;
- sincronizações extensas ainda não usam uma fila de tarefas dedicada.

---

## Próximas evoluções

1. Criar CRUD completo de edição e exclusão com confirmação e auditoria.
2. Adicionar autenticação local, usuários e permissões.
3. Registrar trilha de auditoria por usuário e alteração.
4. Criar tela de revisão/edição do rascunho IA antes do PDF.
5. Permitir promover itens revisados do rascunho para evidências ou anotações.
6. Melhorar o PDF com layout configurável, tabela de evidências, imagens e mapa estático.
7. Adicionar filtros avançados por tipo, confiança, status e período.
8. Adicionar importação/exportação GeoJSON, CSV e JSON estruturado.
9. Implementar backups criptografados e rotação de logs.
10. Adicionar fila de processamento para sincronizações e relatórios extensos.
11. Migrar para PostgreSQL em cenário multiusuário.
12. Criar testes automatizados para coleta, banco, prompts, JSON, mapa e PDF.

---

## Licença e responsabilidade

Antes de distribuir ou utilizar a ferramenta em ambiente institucional, defina licença, política de uso, política de retenção de dados, regras de acesso, rotina de backups e plano de resposta a incidentes. O operador é responsável pelo uso legítimo, seguro e ético das informações processadas.
