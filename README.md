# HOPE — CNPD-OSINT

O **HOPE** é uma aplicação local para auxiliar o gerenciamento de investigações OSINT relacionadas a pessoas desaparecidas. A ferramenta atua como um agregador estruturado de dados: importa registros públicos do Cadastro Nacional de Pessoas Desaparecidas (CNPD), organiza evidências inseridas pelo investigador e oferece recursos para interpretação, análise, georreferenciamento, enriquecimento assistido por IA local e documentação dos casos.

O sistema não substitui autoridades competentes, protocolos institucionais ou validação humana. Seu objetivo é apoiar a organização do trabalho investigativo, preservar fontes e evidências, reduzir a dispersão de informações e facilitar a produção de rascunhos e relatórios revisáveis.

> **Uso responsável:** informações sobre pessoas desaparecidas são sensíveis. Utilize o sistema somente em ambiente controlado, com finalidade legítima, observando a legislação aplicável, a privacidade e a segurança dos dados. Uma ausência no painel público não é prova de localização, óbito, encerramento ou resolução de um caso.

---

## Finalidade

Investigações de pessoas desaparecidas normalmente envolvem informações distribuídas entre portais públicos, pesquisas abertas, consultas com operadores avançados, redes sociais, documentos, imagens, contatos, relatos e referências geográficas.

O HOPE centraliza esses elementos por caso para permitir que o investigador:

- mantenha os dados públicos de origem separados dos dados investigativos;
- registre fonte, data, contexto e nível de confiança de cada achado;
- diferencie dados brutos, fatos confirmados, hipóteses e pendências;
- relacione pessoas próximas, contas sociais, telefones, e-mails e URLs;
- represente locais relevantes em um mapa;
- preserve mídias e hashes para rastreabilidade básica;
- utilize um modelo de linguagem local para organizar um rascunho analítico;
- revise o rascunho antes da criação do relatório PDF.

A aplicação foi projetada para uso local, utilizando FastAPI, SQLite, Leaflet, OpenStreetMap, ReportLab e Ollama.

---

## Funcionalidades

### Integração com CNPD

- Consulta ao painel público do Cadastro Nacional de Pessoas Desaparecidas.
- Coleta paginada por API.
- Requisição `POST` para o endpoint de filtro:

  ```text
  https://cnpd.mj.gov.br/api/api/painel-publico/desaparecidos/filtrar
  ```

- Parâmetros de ordenação e página.
- Preservação do JSON bruto de cada página.
- Normalização dos registros em SQLite.
- Identificação estável por `cnpd_id`.
- Histórico de coletas, páginas, registros e erros.
- Atualização de casos existentes sem duplicação.

### Dados oficiais armazenados

Quando disponíveis no retorno do CNPD:

- ID CNPD;
- nome;
- idade atual;
- idade na data do desaparecimento;
- sexo;
- raça/cor;
- local e UF de registro;
- data do desaparecimento;
- data do registro;
- indicador de localização confirmada;
- hash do objeto original;
- primeira e última coleta;
- JSON original retornado pela fonte;
- URL dos metadados da imagem principal.

### Imagens oficiais CNPD

O endpoint de imagem principal retorna metadados JSON e o conteúdo da imagem em Base64, no campo:

```text
arquivoCnpd.arquivoDTO.conteudo
```

A aplicação:

- extrai o Base64;
- decodifica a imagem;
- reconhece formatos JPEG, PNG, GIF e WEBP;
- salva a mídia em diretório local;
- calcula SHA-256;
- registra os metadados no banco;
- apresenta a imagem no dashboard;
- pode incluir a mídia no PDF.

### Dashboard de casos

- Listagem dos casos armazenados localmente.
- Busca por nome, ID CNPD ou localidade.
- Filtro por UF.
- Filtro por status da fonte.
- Dashboard individual por caso.
- Dados oficiais e imagens associadas.
- Histórico de sincronizações.
- Evidências, pessoas, redes, localizações, mídias e anotações.

### Evidências e pesquisas abertas

O investigador pode registrar:

- resultados de pesquisas abertas;
- consultas e Google Dorks;
- URLs;
- e-mails;
- telefones;
- usernames;
- IDs de perfis;
- redes sociais;
- notícias;
- documentos;
- observações;
- dados livres.

Cada evidência pode conter:

- tipo;
- título ou consulta;
- valor principal;
- descrição/contexto;
- URL da fonte;
- data do evento;
- classificação;
- nível de confiança;
- status de verificação;
- data de criação e atualização.

Classificações recomendadas:

```text
DADO_BRUTO
FATO_CONFIRMADO
HIPOTESE
PENDENCIA
```

### Pessoas relacionadas

Permite cadastrar parentes, amigos, conhecidos e outros vínculos relevantes:

- nome;
- tipo de relação;
- descrição;
- e-mail;
- telefone;
- localidade;
- URL da fonte;
- nível de confiança;
- status de verificação.

### Redes sociais

Permite registrar contas associadas ao desaparecido ou a pessoas relacionadas:

- plataforma;
- username;
- ID da conta;
- URL do perfil;
- nome de exibição;
- observação;
- fonte;
- nível de confiança;
- status de verificação.

### Upload de imagens

- Upload de imagens pelo dashboard.
- Limite inicial de 10 MB.
- Validação de conteúdo de imagem.
- Salvamento do arquivo no diretório local.
- Conversão para Base64.
- Armazenamento do Base64 na tabela `midias`.
- Hash SHA-256.
- Nome, MIME, tamanho, descrição e data.
- Lista/galeria de imagens por caso.
- Inclusão das imagens no relatório PDF.

O arquivo também é preservado em disco para facilitar visualização, backup e exportação.

### Localizações e mapa

- Cadastro de latitude e longitude.
- Título/flag do ponto.
- Tipo de local.
- Data do evento.
- URL/fonte.
- Descrição.
- Nível de confiança.
- Mapa Leaflet.
- Camada OpenStreetMap.
- Marcadores por caso.
- Zoom automático para pontos únicos ou múltiplos.
- Inclusão de mapa estático no PDF.

Tipos de local:

```text
ULTIMO_LOCAL_CONHECIDO
LOCAL_DESAPARECIMENTO
AVISTAMENTO
RESIDENCIA
OUTRO
```

### Anotações e análise

- Campo livre para informações adicionais.
- Anotações de análise.
- Categorias para fatos, hipóteses, pendências e próximos passos.
- Separação entre informação observada e interpretação.

Categorias:

```text
ANOTACAO
FATO_CONFIRMADO
HIPOTESE
PENDENCIA
PROXIMO_PASSO
```

### Relatórios PDF

- Geração a partir do dashboard do caso.
- Abertura em nova aba.
- Dados oficiais do caso.
- Evidências e pesquisas abertas.
- Pessoas relacionadas.
- Contas sociais.
- Imagens do CNPD e do investigador.
- Mapa estático baseado nas coordenadas registradas.
- Lista textual dos pontos geográficos.
- Anotações analíticas.
- Hash SHA-256 do PDF.
- Registro do relatório na tabela `relatorios`.
- Aviso de revisão humana.

---

## Integração com Ollama e Qwen

O HOPE utiliza o Ollama local para gerar um **rascunho estruturado de enriquecimento analítico** a partir dos dados já armazenados no caso.

O modelo não realiza buscas externas, não altera automaticamente o banco, não publica conteúdo e não deve produzir conclusões autônomas. A saída precisa ser revisada pelo investigador antes de ser utilizada em um relatório final.

### Modelo configurado

```text
qwen3.5:latest
```

### API local

A API padrão do Ollama é:

```text
http://127.0.0.1:11434
```

O HOPE utiliza o endpoint:

```text
POST http://127.0.0.1:11434/api/generate
```

### Conteúdo enviado ao modelo

O serviço prepara um contexto resumido contendo:

- dados oficiais do CNPD;
- evidências cadastradas;
- pessoas relacionadas;
- contas sociais;
- pontos geográficos;
- anotações;
- resumo das mídias disponíveis.

O conteúdo Base64 das imagens não é enviado ao modelo. Isso reduz o tamanho do prompt e evita expor bytes de arquivos sem necessidade.

### Saída estruturada

A integração utiliza JSON estruturado com campos como:

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

As hipóteses possuem campos próprios para:

- descrição;
- base disponível;
- limitações.

Isso ajuda a evitar que inferências sejam apresentadas como fatos.

### Regras do prompt

O serviço orienta o modelo a:

- usar somente os dados fornecidos;
- não inventar nomes, datas, locais, vínculos ou eventos;
- não transformar dado bruto em fato confirmado;
- indicar lacunas como pendências;
- manter linguagem neutra e cautelosa;
- não sugerir assédio, exposição, rastreamento invasivo ou contato indevido;
- produzir próximos passos legais, proporcionais e verificáveis;
- retornar somente o JSON solicitado.

### Preparação do Ollama

Verifique a instalação:

```powershell
ollama --version
```

Baixe o modelo:

```powershell
ollama pull qwen3.5:latest
```

Faça um teste interativo:

```powershell
ollama run qwen3.5:latest
```

No prompt do modelo:

```text
Responda somente: OK
```

Saia com:

```text
/bye
```

Se a API não estiver disponível, inicie o serviço:

```powershell
ollama serve
```

Teste via PowerShell:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:11434/api/generate" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"model":"qwen3.5:latest","prompt":"Responda somente OK.","stream":false}'
```

A resposta deve conter uma propriedade semelhante a:

```json
{
  "response": "OK",
  "done": true
}
```

### Gerar rascunho no dashboard

1. Inicie o HOPE.
2. Abra um caso.
3. Cadastre ou revise evidências, pessoas, perfis, pontos e anotações.
4. Clique em **Gerar rascunho com IA**.
5. Revise o rascunho em nova aba.
6. Corrija ou descarte formulações inadequadas.
7. Gere o PDF somente depois da revisão.

O rascunho é persistido na tabela:

```text
rascunhos_ia
```

São registrados:

- ID do caso;
- modelo utilizado;
- contexto resumido enviado;
- resposta JSON;
- métricas de geração;
- status;
- data de criação e atualização.

### Variáveis de configuração

No arquivo `app/config.py`:

```python
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_GENERATE_URL = f"{OLLAMA_BASE_URL}/api/generate"
OLLAMA_MODEL = "qwen3.5:latest"
OLLAMA_TIMEOUT_SECONDS = 240
OLLAMA_TEMPERATURE = 0.2
OLLAMA_NUM_PREDICT = 2600
```

Use temperatura baixa para priorizar consistência e fidelidade aos dados armazenados.

### Teste direto do serviço

Crie ou utilize `testar_ollama.py`:

```python
from app.services.investigation_service import build_case_context
from app.services.ollama_service import generate_report_draft

CNPD_ID = 215477

context = build_case_context(CNPD_ID)
result = generate_report_draft(context)

print("Modelo:", result["model"])
print("Métricas:", result["metrics"])
print("Rascunho:")
print(result["draft"])
```

Execute:

```powershell
python .\testar_ollama.py
```

### Falhas comuns

#### Ollama não encontrado

```text
Connection refused
```

Solução:

```powershell
ollama serve
```

#### Modelo inexistente

```text
model not found
```

Solução:

```powershell
ollama pull qwen3.5:latest
```

#### Tempo excedido

Modelos locais podem levar tempo para carregar e gerar. Aumente `OLLAMA_TIMEOUT_SECONDS` e verifique memória RAM, VRAM e tamanho do modelo.

#### JSON inválido

O serviço valida a resposta com `json.loads`. Se o modelo retornar texto adicional, verifique se o campo `format` com JSON Schema está sendo enviado ao endpoint.

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
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── routers/
│   │   ├── cases.py
│   │   ├── reports.py
│   │   ├── sync.py
│   │   └── ai.py
│   ├── services/
│   │   ├── cnpd_client.py
│   │   ├── investigation_service.py
│   │   ├── ollama_service.py
│   │   ├── report_service.py
│   │   └── sync_service.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── sync.html
│   │   ├── case_detail.html
│   │   └── ai_draft.html
│   └── static/
│       └── css/
│           └── app.css
├── data/
│   ├── cnpd.db
│   ├── raw/cnpd/
│   ├── images/source/
│   ├── images/uploads/
│   └── reports/
└── logs/
```

---

## Requisitos

- Python 3.11 ou superior;
- FastAPI e Uvicorn;
- SQLite, incluído no Python;
- requests;
- Jinja2;
- python-multipart;
- ReportLab;
- Ollama instalado localmente para o enriquecimento com IA;
- modelo `qwen3.5:latest` baixado;
- navegador moderno;
- internet para o CNPD, Leaflet e tiles OpenStreetMap.

---

## Instalação no Windows

Abra o PowerShell na pasta do projeto:

```powershell
cd H:\3.Missing_person_project\cnpd-osint
```

Crie e ative o ambiente virtual:

```powershell
python -m venv env
.\env\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r .\requirements.txt
```

Prepare o Ollama:

```powershell
ollama pull qwen3.5:latest
```

Inicie a aplicação:

```powershell
python .\run.py
```

Acesse:

```text
http://127.0.0.1:8000
```

---

## Instalação no Linux/macOS

```bash
cd cnpd-osint
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
ollama pull qwen3.5:latest
python run.py
```

Acesse:

```text
http://127.0.0.1:8000
```

---

## Primeiro uso

1. Abra `http://127.0.0.1:8000/sincronizar`.
2. Use página inicial `0` e máximo de páginas `1`.
3. Faça uma coleta sem imagens para validar a persistência.
4. Abra a lista de casos.
5. Escolha um caso.
6. Cadastre evidências, pessoas, perfis, localizações e anotações.
7. Faça upload de imagens, se necessário.
8. Clique em **Gerar rascunho com IA**.
9. Revise o resultado.
10. Clique em **Gerar relatório PDF**.

---

## Banco de dados

O banco é criado em:

```text
data/cnpd.db
```

### Tabelas principais

| Tabela | Finalidade |
|---|---|
| `casos` | Dados normalizados do CNPD |
| `coletas` | Histórico de sincronizações |
| `casos_coleta` | Presença do caso em cada coleta |
| `midias` | Imagens oficiais e uploads |
| `evidencias` | Pesquisas, URLs, e-mails, telefones e achados |
| `pessoas_relacionadas` | Pessoas próximas e vínculos |
| `contas_sociais` | Perfis, usernames e IDs |
| `pontos_geograficos` | Coordenadas e contexto espacial |
| `anotacoes` | Análises, fatos, hipóteses e pendências |
| `rascunhos_ia` | Contextos e respostas geradas pelo Ollama |
| `relatorios` | PDFs e seus hashes |

### Status de fonte

```text
ATIVO_NA_FONTE
AUSENTE_EM_UMA_COLETA
AUSENTE_EM_MULTIPLAS_COLETAS
PENDENTE_DE_REVISAO
ARQUIVADO_POR_CONFIRMACAO
```

Uma ausência em uma coleta não é uma conclusão sobre o destino da pessoa.

---

## Armazenamento local

```text
data/cnpd.db
 data/raw/cnpd/coleta_{id}/pagina_00000.json
 data/images/source/{cnpd_id}/
 data/images/uploads/{cnpd_id}/
 data/reports/
```

---

## Diagnóstico

Testar sincronização sem interface:

```powershell
python .\sincronizar_teste.py
```

Diagnosticar SQLite:

```powershell
python .\diagnostico.py
```

Testar Ollama diretamente:

```powershell
python .\testar_ollama.py
```

Verificar CSS:

```text
http://127.0.0.1:8000/static/css/app.css
```

---

## Segurança e ética

- Mantenha a aplicação local ou em rede controlada.
- Não exponha as portas `8000` ou `11434` diretamente na internet.
- Proteja o banco, mídias, prompts, respostas do modelo e backups.
- Não envie Base64 de imagens ao modelo sem necessidade.
- Não registre no prompt informações que não sejam necessárias para o rascunho.
- Diferencie dados brutos, fatos confirmados, hipóteses e pendências.
- Não automatize contato com familiares, terceiros ou contas sociais.
- Não use reconhecimento facial ou associação automática de identidade sem base legal, governança e revisão especializada.
- Revise todo conteúdo produzido pelo Ollama antes de gerar ou compartilhar um relatório.
- Preserve o contexto de entrada e a resposta do modelo para auditoria.
- Faça backups regulares e considere criptografia para dados sensíveis.

---

## Limitações atuais

- Não há autenticação ou controle de permissões por usuário;
- não há trilha completa de auditoria;
- edição e exclusão ainda podem ser limitadas em alguns recursos;
- o mapa depende de CDN Leaflet e tiles OpenStreetMap;
- a geração do mapa estático depende da disponibilidade dos tiles;
- o Ollama pode produzir omissões ou interpretações inadequadas;
- o rascunho IA não é uma conclusão investigativa;
- não há automação OSINT autônoma;
- não há garantia de que a ausência de um caso na fonte represente resolução.

---

## Próximas evoluções

1. Adicionar autenticação local e perfis de investigador.
2. Implementar trilha de auditoria de alterações.
3. Adicionar edição e exclusão completas com confirmação.
4. Incorporar revisão/aprovação do rascunho IA no dashboard.
5. Permitir converter itens do rascunho em anotações ou evidências após revisão.
6. Inserir imagens e mapa estático no PDF com layout configurável.
7. Implementar backups criptografados.
8. Adicionar fila para sincronização e geração de relatórios.
9. Migrar para PostgreSQL em ambiente multiusuário.
10. Criar testes automatizados para banco, coleta, prompts, JSON Schema e PDF.

---

## Licença e responsabilidade

Antes de distribuir ou utilizar a aplicação em contexto institucional, defina uma licença, política de uso, controles de acesso, procedimento de retenção, rotina de backups e plano de resposta a incidentes. O operador é responsável pelo uso legítimo, seguro e ético das informações processadas.
