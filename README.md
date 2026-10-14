# AS/400 Interface

Interface web para consulta e CRUD de pessoas em um IBM i (AS/400) remoto
(pub400.com), com integracao a PostgreSQL e MongoDB. Inclui um chat IA que
traduz perguntas em linguagem natural para SQL.

Este repositorio contem **duas partes**:

1. **Aplicacao Django** (raiz do repo) — interface web
2. **API Java Spring Boot** (`ceps-api/`) — API REST que expoe dados de CEP do IBM i

## Stack

### Django (raiz)

- Django 6.0.7
- Python 3.13
- JPype + jt400.jar (conexao JDBC com AS/400)
- PostgreSQL (psycopg2-binary)
- MongoDB (pymongo)
- DeepSeek (chat IA via `openai` SDK)
- Gunicorn + systemd (producao)

### Java (`ceps-api/`)

- Java + Spring Boot
- Maven (wrapper incluso: `mvnw`)

## Estrutura

    as400_interface/
    +-- as400_project/              # Configuracao Django
    |   +-- settings.py
    |   +-- urls.py
    |   +-- wsgi.py
    +-- pessoas/                    # App principal
    |   +-- templates/pessoas/
    |   |   +-- chat.html
    |   |   +-- lista_paginada.html
    |   |   +-- form_pessoa.html
    |   |   +-- detalhe.html
    |   |   +-- lista_ceps.html
    |   |   +-- estabelecimento.html
    |   |   +-- confirmar_exclusao.html
    |   |   +-- erro.html
    |   +-- as400_conn.py           # Conexao JDBC com AS/400
    |   +-- pool.py                 # Conexao unica JDBC (isValid + max_age)
    |   +-- ceps.py                 # Busca de CEP
    |   +-- chat.py                 # Pipeline do chat IA
    |   +-- contexto.py             # Contexto da conversa
    |   +-- validators.py           # Validacao de CPF, email, etc
    |   +-- views.py                # Views (1100+ linhas)
    +-- ceps-api/                   # Projeto Java (Spring Boot)
    |   +-- src/
    |   +-- pom.xml
    |   +-- mvnw
    |   +-- mvnw.cmd
    +-- lib/
    |   +-- README.md               # Instrucoes pra baixar jt400.jar
    +-- conecta_as400.py            # Script de teste de conexao
    +-- teste_ibm_db.py             # Teste com ibm_db
    +-- teste_jaydebeapi.py         # Teste com JayDeBeApi
    +-- teste_jpype.py              # Teste com JPype
    +-- teste_jt400.py              # Teste com jt400
    +-- manage.py
    +-- requirements.txt
    +-- runtime.txt

## Como rodar local

### Pre-requisitos

- Python 3.13
- JDK 11+ (a JVM e necessaria pro JDBC)
- Credenciais de um IBM i (por padrao, usa o `pub400.com`)
- PostgreSQL rodando (usado pra sessao/admin)

### Django

    python -m venv env_django
    source env_django/bin/activate
    pip install -r requirements.txt
    cp .env.example .env            # preencher valores
    (baixar lib/jt400.jar - ver lib/README.md)
    python manage.py migrate
    python manage.py runserver 8001

Acessa em http://localhost:8001/

### Java (ceps-api)

    cd ceps-api
    ./mvnw spring-boot:run

## Requisitos de dados

Este repositorio **nao inclui** o banco AS/400 nem os dados de pessoas.
A aplicacao se conecta a um IBM i remoto e le a tabela `AROSASSE1.PESSOAS`
que vive la.

Para rodar, voce precisa:

1. **Criar conta no `pub400.com`** (IBM i publico de testes) ou ter acesso
   a outro IBM i.
2. Colocar as credenciais no `.env` (`AS400_HOST`, `AS400_USER`,
   `AS400_PASSWORD`, `AS400_LIBRARY`).
3. **Criar a tabela `AROSASSE1.PESSOAS`** no IBM i. O DDL nao esta
   versionado — a tabela existia no ambiente original e precisa ser
   recriada manualmente (colunas: `ID_PESSOA`, `CPF`, `NOMECOMPL`,
   `EMAIL`, `TELEFONE`, `DATA_NASC`, `STATUS`, `CEP`, `ESTADO`,
   `CIDADE`, `BAIRRO`, `ENDERECO`, `NUMERO`, `COMPL00001`,
   `DATACADAST`).
4. Baixar o `lib/jt400.jar` (nao versionado — ver `lib/README.md`).

Sem esses passos, o app sobe mas nao consegue listar nem cadastrar nada.

### Variaveis de ambiente

Ver `.env.example`. As principais:

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` — Django padrao
- `AS400_HOST`, `AS400_USER`, `AS400_PASSWORD`, `AS400_LIBRARY` — IBM i
- `DEEPSEEK_API_KEY` — chave da API do chat

## Endpoints

| Metodo | URL | O que faz |
|---|---|---|
| GET | `/` | Lista paginada de pessoas |
| GET | `/pessoas/paginadas/` | Lista com filtros avancados |
| GET | `/pessoas/<id>/` | Detalhe de uma pessoa |
| GET/POST | `/pessoas/novo/` | Cadastra nova pessoa |
| GET/POST | `/pessoas/<id>/editar/` | Edita pessoa |
| GET/POST | `/pessoas/<id>/excluir/` | Exclui pessoa |
| GET | `/pessoas/exportar/` | Exporta CSV |
| GET | `/api/pessoas/` | API JSON |
| GET | `/buscar-cep/` | Busca CEP via AJAX |
| GET | `/lista-ceps/` | Lista CEPs |
| GET | `/estabelecimento/<cep>/` | Estabelecimentos do CEP |
| GET/POST | `/chat-pessoas/` | Chat IA |
| GET | `/testar-deepseek/` | Testa conexao com DeepSeek |
| GET | `/health/` | Health check leve |
| GET | `/health/deep/` | Health check profundo (testa AS/400) |

## Chat IA

O pipeline do chat:

    Pergunta (PT-BR)
      -> gerar_sql_com_contexto   (DeepSeek gera o SQL, com contexto)
      -> executar_sql             (roda no AS/400 via JDBC)
      -> gerar_resposta_com_dados (DeepSeek transforma os dados em texto)

Arquivos:

- `pessoas/chat.py` — pipeline principal
- `pessoas/contexto.py` — mantem contexto da conversa (ultimas 5 interacoes,
  extraidas via IA)
- DeepSeek via `openai` SDK apontando para `https://api.deepseek.com/v1`

## Deploy

Na maquina NoteNeto:

    ./deploy.sh as400

## Ambiente

- **Local:** http://localhost:8001
- **Producao:** https://as400.arosasse.tech

## Testes

Os arquivos `teste_*.py` na raiz sao scripts de teste de conexao com o
AS/400 usando diferentes bibliotecas (ibm_db, JayDeBeApi, JPype, jt400).
Servem pra diagnosticar qual driver funciona melhor em cada ambiente.

## Sobre o `ceps-api/`

O `ceps-api/` e uma aplicacao **Java Spring Boot** que expoe os dados de
CEP da tabela `AROSASSE1.CEPS` do IBM i via API REST. Ele **nao** e
chamado pela aplicacao Django em runtime — os dois convivem no mesmo
repositorio por conveniencia, mas sao pecas independentes.

O que ele faz:

- `@RestController` em `CepController.java`
- Le a tabela `AROSASSE1.CEPS` via JDBC (`DriverManager`)
- Expoe pelo menos 1 endpoint REST: `GET /ceps` (retorna `id`, `uf`,
  `cidade`, `cepDe`, `cepAte`)
- Usa a variavel de ambiente `AS400_PASSWORD` (nao tem senha hardcoded)

Como rodar local:

    cd ceps-api
    ./mvnw spring-boot:run

O `application.properties` em `src/main/resources/` tem as configuracoes
de conexao. Se for rodar dentro do IBM i, e preciso empacotar com
`./mvnw package` e copiar o `.jar` gerado.

## Repositorios relacionados

- [cnpj_interface](https://github.com/antoniorosasse/cnpj_interface)
- [menu_interface](https://github.com/antoniorosasse/menu_interface)
- [ProjetoCargaDados](https://github.com/antoniorosasse/ProjetoCargaDados)
