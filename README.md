# HOPE — CNPD-OSINT

O **HOPE** é uma aplicação local para auxiliar o gerenciamento de investigações OSINT relacionadas a pessoas desaparecidas. A ferramenta funciona como um agregador estruturado de dados: importa registros públicos do Cadastro Nacional de Pessoas Desaparecidas (CNPD), organiza evidências inseridas pelo investigador e oferece recursos para interpretação, análise, georreferenciamento e documentação dos casos.

A aplicação não substitui autoridades competentes, protocolos institucionais ou validação humana. Seu objetivo é apoiar a organização do trabalho investigativo, preservar fontes e evidências, reduzir dispersão de informações e facilitar a produção de relatórios revisáveis.

> **Uso responsável:** informações sobre pessoas desaparecidas são sensíveis. Utilize o sistema somente em ambiente controlado, com finalidade legítima, observando a legislação aplicável, a privacidade e a segurança dos dados. Uma ausência no painel público não é prova de localização, óbito, encerramento ou resolução de um caso.

---

## Finalidade

Investigações de pessoas desaparecidas frequentemente envolvem informações dispersas entre portais públicos, consultas abertas na internet, perfis sociais, fontes jornalísticas, documentos, imagens, contatos, relatos e pontos geográficos. O HOPE centraliza esses elementos por caso, permitindo que o investigador:

- mantenha o registro público de origem separado de dados investigativos;
- registre a origem, o contexto e o grau de confiança de cada achado;
- diferencie fatos confirmados, dados brutos, hipóteses e pendências;
- relacione pessoas próximas, contas sociais, telefones, e-mails e URLs;
- represente locais relevantes em mapa;
- preserve mídias e hashes para rastreabilidade básica;
- gere relatórios operacionais para revisão humana.

O sistema foi projetado para ser executado localmente, usando SQLite como banco de dados e FastAPI como backend web.

---

## Funcionalidades

### Integração com CNPD

- Consulta ao painel público do Cadastro Nacional de Pessoas Desaparecidas.
- Coleta paginada de registros por API.
- Uso do endpoint público observado:

  ```text
  POST https://cnpd.mj.gov.br/api/api/painel-publico/desaparecidos/filtrar
  ```

- Paginação por parâmetro `pagina`.
- Ordenação padrão por registros mais recentes.
- Preservação do JSON bruto de cada página coletada.
- Normalização de dados no banco SQLite.
- Identificação estável por `cnpd_id`.
- Histórico de coletas, páginas processadas, quantidade de registros e erros.
- Atualização de registros já existentes sem duplicar casos.

### Dados oficiais armazenados

Quando presentes no retorno do CNPD, são registrados:

- ID CNPD;
- nome;
- idade atual;
- idade na data do desaparecimento;
- sexo;
- raça/cor;
- município/local de registro;
- UF;
- data do desaparecimento;
- data do registro;
- indicador de localização confirmada;
- hash do objeto recebido da fonte;
- data da primeira e da última coleta;
- JSON original da fonte;
- URL de metadados da imagem oficial.

### Imagens oficiais do CNPD

- Consulta do endpoint de imagem principal por ID CNPD.
- Leitura dos metadados JSON retornados pela fonte.
- Extração da imagem codificada em Base64 no campo:

  ```text
  arquivoCnpd.arquivoDTO.conteudo
  ```

- Decodificação da imagem para arquivo local.
- Validação básica de assinatura de formatos JPEG, PNG, GIF e WEBP.
- Armazenamento da imagem original no diretório do projeto.
- Cálculo de hash SHA-256.
- Registro da mídia no banco de dados.

### Dashboard de casos

- Listagem de casos armazenados localmente.
- Busca por nome, ID CNPD ou localidade.
- Filtro por UF.
- Filtro por status da fonte.
- Página individual para cada caso.
- Exibição dos dados oficiais do CNPD.
- Exibição de imagem oficial, quando baixada.
- Histórico de sincronizações em que o caso foi encontrado.

### Pesquisas abertas e evidências

O dashboard permite registrar dados produzidos ou encontrados pelo investigador, incluindo:

- consultas abertas na internet;
- Google Dorks e termos de busca;
- resultados de pesquisa;
- URLs;
- notícias;
- documentos;
- e-mails;
- telefones;
- usernames;
- IDs de contas;
- perfis sociais;
- observações e outros achados.

Cada evidência pode conter:

- tipo;
- título;
- valor principal;
- descrição/contexto;
- URL da fonte;
- data do evento;
- classificação;
- nível de confiança;
- status de verificação;
- data de criação e atualização.

Classificações previstas:

```text
DADO_BRUTO
FATO_CONFIRMADO
HIPOTESE
PENDENCIA
```

### Pessoas relacionadas

Permite cadastrar parentes, amigos, conhecidos ou outros vínculos relevantes ao caso:

- nome;
- tipo de relação;
- descrição da relação;
- e-mail;
- telefone;
- localidade;
- URL/fonte;
- nível de confiança;
- status de verificação.

### Redes sociais

Permite registrar perfis associados ao desaparecido ou a pessoas relacionadas:

- plataforma;
- username;
- ID do perfil;
- URL do perfil;
- nome de exibição;
- observações;
- fonte;
- nível de confiança;
- status de verificação.

### Imagens inseridas pelo investigador

- Upload de imagens pelo dashboard do caso.
- Limite inicial de 10 MB por arquivo.
- Validação de arquivos de imagem.
- Armazenamento físico em diretório local.
- Conversão e armazenamento do conteúdo em Base64 na tabela `midias`.
- Cálculo de SHA-256.
- Registro de nome, MIME, tamanho, descrição e data.
- Exibição das imagens cadastradas no dashboard.

> O arquivo é preservado em disco para visualização e backup mais eficientes. O Base64 é mantido no banco para atender ao requisito de vinculação do conteúdo ao caso.

### Localizações e mapa

- Cadastro manual de latitude e longitude.
- Título/flag descritiva do ponto.
- Tipo de local.
- Data do evento.
- URL/fonte.
- Descrição e nível de confiança.
- Mapa dinâmico com Leaflet.
- Camada cartográfica OpenStreetMap.
- Marcadores para os pontos cadastrados.
- Zoom automático para um ponto ou conjunto de pontos.

Tipos de local disponíveis:

```text
ULTIMO_LOCAL_CONHECIDO
LOCAL_DESAPARECIMENTO
AVISTAMENTO
RESIDENCIA
OUTRO
```

### Anotações e análise

- Campo livre para dados adicionais.
- Registro de anotações analíticas.
- Categorias para fatos, hipóteses, pendências e próximos passos.
- Separação conceitual entre informação observada e interpretação investigativa.

Categorias sugeridas:

```text
ANOTACAO
FATO_CONFIRMADO
HIPOTESE
PENDENCIA
PROXIMO_PASSO
```

### Relatórios PDF

- Botão no dashboard para gerar relatório por caso.
- Abertura do PDF em nova aba do navegador.
- Registro do arquivo em `data/reports/`.
- Hash SHA-256 do PDF.
- Registro de metadados na tabela `relatorios`.
- Inclusão de dados principais do caso, evidências, pessoas relacionadas, redes sociais, pontos geográficos e anotações.
- Aviso explícito de que o documento é operacional e exige revisão humana.

A versão atual gera um relatório estruturado sem inferências automáticas. A integração com Ollama/Qwen pode ser incorporada posteriormente para produzir **rascunhos revisáveis**, nunca conclusões autônomas.

---

## Arquitetura

```text
cnpd-osint/
├── README.md
├── requirements.txt
├── run.py
├── diagnostico.py
├── sincronizar_teste.py
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── cases.py
│   │   ├── reports.py
│   │   └── sync.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cnpd_client.py
│   │   ├── investigation_service.py
│   │   ├── report_service.py
│   │   └── sync_service.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── sync.html
│   │   └── case_detail.html
│   └── static/
│       └── css/
│           └── app.css
├── data/
│   ├── cnpd.db
│   ├── raw/
│   │   └── cnpd/
│   ├── images/
│   │   ├── source/
│   │   └── uploads/
│   ├── reports/
│   └── exports/
└── logs/
```

---

## Requisitos

- Python 3.11 ou superior;
- conexão de rede com o painel público CNPD;
- navegador moderno;
- Windows, Linux ou macOS;
- conexão com a internet para a camada OpenStreetMap e bibliotecas Leaflet carregadas por CDN.

---

## Instalação

### Windows PowerShell

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

Inicie a aplicação:

```powershell
python .\run.py
```

Abra no navegador:

```text
http://127.0.0.1:8000
```

### Linux/macOS

```bash
cd cnpd-osint

python3 -m venv env
source env/bin/activate

pip install -r requirements.txt
python run.py
```

Abra no navegador:

```text
http://127.0.0.1:8000
```

---

## Primeiro uso

1. Inicie o servidor:

   ```powershell
   python .\run.py
   ```

2. Abra a tela de sincronização:

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

5. Após a conclusão, abra:

   ```text
   http://127.0.0.1:8000/
   ```

6. Clique em **Abrir** para acessar o dashboard de um caso.

7. Registre evidências, pessoas relacionadas, redes sociais, localizações, imagens e anotações.

8. Use **Gerar relatório PDF** para produzir um documento por caso.

9. Para baixar imagens oficiais, execute nova sincronização marcando a opção correspondente. Comece com uma página para avaliar volume e desempenho.

---

## Banco de dados

O HOPE utiliza SQLite. O banco é criado em:

```text
data/cnpd.db
```

### Tabelas principais

| Tabela | Finalidade |
|---|---|
| `casos` | Dados normalizados obtidos do CNPD |
| `coletas` | Histórico de sincronizações |
| `casos_coleta` | Relação entre um caso e uma coleta |
| `midias` | Imagens oficiais e uploads do investigador |
| `evidencias` | Pesquisas, URLs, e-mails, telefones e outros achados |
| `pessoas_relacionadas` | Parentes, conhecidos e vínculos registrados |
| `contas_sociais` | Perfis, usernames e IDs sociais |
| `pontos_geograficos` | Coordenadas e contexto geográfico |
| `anotacoes` | Análises, fatos, hipóteses e pendências |
| `relatorios` | Metadados, hash e referência a relatórios PDF |

### Status de fonte

```text
ATIVO_NA_FONTE
AUSENTE_EM_UMA_COLETA
AUSENTE_EM_MULTIPLAS_COLETAS
PENDENTE_DE_REVISAO
ARQUIVADO_POR_CONFIRMACAO
```

> Uma ausência na fonte é apenas um evento operacional que deve ser revisado por uma pessoa autorizada. Não é uma conclusão sobre o caso.

---

## Armazenamento local

### Banco SQLite

```text
data/cnpd.db
```

### Respostas brutas da fonte

```text
data/raw/cnpd/coleta_{id}/pagina_00000.json
```

### Imagens oficiais CNPD

```text
data/images/source/{cnpd_id}/
```

### Uploads de investigador

```text
data/images/uploads/{cnpd_id}/
```

### Relatórios

```text
data/reports/
```

---

## Diagnóstico e testes

### Testar sincronização sem interface web

```powershell
python .\sincronizar_teste.py
```

O resultado esperado em uma página é aproximadamente:

```text
status: COMPLETA
pages_read: 1
records_read: 30
```

### Diagnosticar banco SQLite

```powershell
python .\diagnostico.py
```

O script informa:

- caminho absoluto do banco utilizado;
- existência e tamanho do arquivo SQLite;
- tabelas criadas;
- histórico de coletas;
- total de casos;
- primeiros casos persistidos.

### Verificar CSS

Abra diretamente no navegador:

```text
http://127.0.0.1:8000/static/css/app.css
```

Se fizer alterações visuais, use `Ctrl+F5` no navegador para ignorar o cache.

---

## Segurança, privacidade e ética

- Mantenha a aplicação em computador ou rede controlada.
- Não publique o servidor FastAPI diretamente na internet.
- Proteja o banco, os diretórios de mídia e os backups.
- Registre fonte, data, contexto e confiança para cada evidência.
- Diferencie dados brutos, fatos confirmados, hipóteses e pendências.
- Não automatize contato com familiares, terceiros, contas sociais ou possíveis envolvidos.
- Não use reconhecimento facial, associação automática de identidade ou tomada automatizada de decisão sem base legal, governança, autorização e revisão humana apropriadas.
- Revise o conteúdo antes de gerar, compartilhar ou encaminhar um relatório.
- Faça backups regulares do banco SQLite e dos diretórios `data/images/` e `data/reports/`.

---

## Limitações atuais

- Não há autenticação ou controle de permissões por usuário;
- não há trilha de auditoria por investigador;
- edição e exclusão completas ainda não foram implementadas para todos os registros;
- o mapa depende de CDN Leaflet e dos tiles do OpenStreetMap;
- não há fila de processamento para coletas extensas;
- a automação OSINT não está implementada;
- a integração Ollama/Qwen ainda não está ativa;
- o mecanismo definitivo para validar varredura integral antes de sinalizar ausências da fonte deve ser tratado com cautela.

---

## Próximas evoluções sugeridas

1. Adicionar CRUD completo para editar e excluir evidências, pessoas, perfis, pontos, mídias e anotações.
2. Adicionar autenticação local, usuários e permissões.
3. Criar trilha de auditoria com autor, data, alteração anterior e alteração posterior.
4. Implementar filtros avançados por tipo de evidência, confiança, verificação e período.
5. Vincular contas sociais diretamente a pessoas relacionadas pelo dashboard.
6. Melhorar a visualização geográfica com ícones e cores por categoria de localização.
7. Importar e exportar GeoJSON, CSV e JSON estruturado por caso.
8. Integrar Ollama com modelo local para gerar rascunhos de relatório revisáveis.
9. Criar tela de revisão/edição do rascunho antes de gerar PDF definitivo.
10. Inserir imagens, tabela de evidências e mapa estático no PDF.
11. Implementar backups criptografados.
12. Migrar para PostgreSQL se houver uso simultâneo por múltiplos investigadores ou maior volume de dados.

---

## Licença e responsabilidade

Antes de distribuir ou utilizar a aplicação em contexto institucional, defina uma licença, política de uso, controles de acesso, procedimento de retenção de dados, rotina de backups e política de resposta a incidentes. O operador é responsável pelo uso legítimo, seguro e ético das informações processadas.
