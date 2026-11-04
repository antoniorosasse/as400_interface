# AS/400 Interface

Interface web para consulta e CRUD de pessoas em um IBM i (AS/400) remoto
(pub400.com), via JDBC. O banco local e **SQLite**, usado só pra sessão e
admin. Inclui um chat IA que traduz perguntas em linguagem natural para SQL.

Este repositório contém **duas partes**:

1. **Aplicação Django** (raiz do repo) — interface web
2. **API Java Spring Boot** (`ceps-api/`) — API REST que expõe dados de CEP do IBM i

## Índice

- [Stack](#stack)
  - [Django (raiz)](#django-raiz)
  - [Java (`ceps-api/`)](#java-ceps-api)
- [Estrutura](#estrutura)
- [Como rodar local](#como-rodar-local)
  - [Pré-requisitos](#pré-requisitos)
  - [Django](#django)
  - [Java (ceps-api)](#java-ceps-api-1)
- [Requisitos de dados](#requisitos-de-dados)
  - [Variáveis de ambiente](#variáveis-de-ambiente)
- [Endpoints](#endpoints)
- [Chat IA](#chat-ia)
- [Deploy](#deploy)
- [Ambiente](#ambiente)
- [Testes](#testes)
- [Sobre o `ceps-api/`](#sobre-o-ceps-api)
- [Repositórios relacionados](#repositórios-relacionados)

## Stack

### Django (raiz)

- Django 6.0.7
- Python 3.13
- JPype + jt400.jar (conexão JDBC com AS/400)
- SQLite (`db.sqlite3`) — apenas sessão, admin e migrations
- Cache LocMem (`as400-cache`, `TIMEOUT=300`)
- DeepSeek (chat IA via `openai` SDK)
- Gunicorn + systemd (produção)

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
    |   +-- static/pessoas/css/
    |   |   +-- sistema.css        # Linguagem visual comum (tabela, pills, tema)
    |   +-- as400_conn.py           # Conexao JDBC com AS/400
    |   +-- pool.py                 # Conexao unica JDBC (isValid + max_age)
    |   +-- ceps.py                 # Busca de CEP
    |   +-- chat.py                 # Pipeline do chat IA
    |   +-- contexto.py             # Contexto da conversa
    |   +-- validators.py           # Validacao de CPF, email, etc
    |   +-- models.py               # Vazio: os dados vem do IBM i via JDBC (sem ORM)
    |   +-- admin.py                # Vazio: nenhum model local registrado
    |   +-- tests.py                # 8 testes automatizados do export CSV
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

## Front-end (tema e CSS)

- Bootstrap 5.3 via CDN (`pessoas/templates/base.html`), com tema claro/escuro
  nativo (`data-bs-theme`) alternado pelo botão da navbar. A escolha fica em
  `localStorage['sistema-tema']` — a mesma chave do `cnpj_interface` (o
  `localStorage` é por origem, então cada subdomínio guarda a própria escolha; a
  chave única é o que permite unificar os módulos depois). `?tema=dark|light`
  força o tema pela URL e o script do `<head>` aplica antes do CSS (sem flash
  branco).
- `pessoas/static/pessoas/css/sistema.css` é a mesma folha do `cnpj_interface`
  (tabela densa, cabeçalho discreto, pills suaves, números alinhados) e a
  transformação de tabela em cartões no celular (`.tabela-cards`, via
  `data-label` de cada `<td>`). As cores saem das variáveis do Bootstrap
  (`--bs-*-bg-subtle`, `--bs-border-color`, `--bs-tertiary-bg`), então o tema
  escuro não precisa de CSS próprio.
- Os estilos locais (`.chat-container`, `.message-*` no chat de pessoas) usam
  as mesmas variáveis; nenhuma cor fixa fora do texto branco sobre `primary`.

## Como rodar local

### Pré-requisitos

- Python 3.13
- JDK 11+ (a JVM é necessária pro JDBC)
- Credenciais de um IBM i (por padrão, usa o `pub400.com`)
- Nenhum servidor de banco local: o `migrate` cria o `db.sqlite3` (sessão/admin)

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

Este repositório **não inclui** o banco AS/400 nem os dados de pessoas.
A aplicação se conecta a um IBM i remoto e le a tabela `AROSASSE1.PESSOAS`
que vive lá.

Para rodar, você precisa:

1. **Criar conta no `pub400.com`** (IBM i público de testes) ou ter acesso
   a outro IBM i.
2. Colocar as credenciais no `.env` (`AS400_HOST`, `AS400_USER`,
   `AS400_PASSWORD`, `AS400_LIBRARY`).
3. **Criar a tabela `AROSASSE1.PESSOAS`** no IBM i. O DDL não está
   versionado — a tabela existia no ambiente original e precisa ser
   recriada manualmente (colunas: `ID_PESSOA`, `CPF`, `NOMECOMPL`,
   `EMAIL`, `TELEFONE`, `DATA_NASC`, `STATUS`, `CEP`, `ESTADO`,
   `CIDADE`, `BAIRRO`, `ENDERECO`, `NUMERO`, `COMPLEMENTO`,
   `DATACADAST`).
4. Baixar o `lib/jt400.jar` (não versionado — ver `lib/README.md`).

Sem esses passos, o app sobe mas não consegue listar nem cadastrar nada.

### Variáveis de ambiente

Ver `.env.example`. As principais:

- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` — Django padrão
- `AS400_HOST`, `AS400_USER`, `AS400_PASSWORD`, `AS400_LIBRARY` — IBM i
- `DEEPSEEK_API_KEY` — chave da API do chat

## Endpoints

| Método | URL | O que faz |
|---|---|---|
| GET | `/` | Home: lista paginada de pessoas (mesma view de `/pessoas/paginadas/`) |
| GET | `/pessoas/` | Redireciona (302) para `/pessoas/paginadas/` |
| GET | `/pessoas/paginadas/` | Lista com filtros avançados |
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
| GET | `/testar-deepseek/` | Testa conexão com DeepSeek |
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
- `pessoas/contexto.py` — mantém contexto da conversa (últimas 5 interações,
  extraídas via IA)
- DeepSeek via `openai` SDK apontando para `https://api.deepseek.com/v1`

## Deploy

Na máquina NoteNeto:

    ./deploy.sh as400

## Ambiente

- **Local:** http://localhost:8001
- **Produção:** https://as400.arosasse.tech

## Testes

Suíte automatizada do app `pessoas` (**8 testes**, todos `SimpleTestCase`):

    python manage.py test pessoas

Eles cobrem o export CSV: streaming UTF-8, fechamento de `ResultSet`/`Statement`
em erro de SQL e em download abortado pelo cliente. O pool JDBC e mockado —
nenhum teste toca no AS/400 real.

Os arquivos `teste_*.py` na raiz são scripts **manuais** de teste de conexão com
o AS/400 usando diferentes bibliotecas (ibm_db, JayDeBeApi, JPype, jt400).
Servem pra diagnosticar qual driver funciona melhor em cada ambiente e não
fazem parte da suite.

## Sobre o `ceps-api/`

O `ceps-api/` é uma aplicação **Java Spring Boot** que expõe os dados de
CEP da tabela `AROSASSE1.CEPS` do IBM i via API REST. Ele **não** é
chamado pela aplicação Django em runtime — os dois convivem no mesmo
repositório por conveniência, mas são peças independentes.

O que ele faz:

- `@RestController` em `CepController.java`
- Lê a tabela `AROSASSE1.CEPS` via JDBC (`DriverManager`)
- Expõe pelo menos 1 endpoint REST: `GET /ceps` (retorna `id`, `uf`,
  `cidade`, `cepDe`, `cepAte`)
- Usa a variável de ambiente `AS400_PASSWORD` (não tem senha hardcoded)

Como rodar local:

    cd ceps-api
    ./mvnw spring-boot:run

O `application.properties` em `src/main/resources/` tem as configurações
de conexão. Se for rodar dentro do IBM i, é preciso empacotar com
`./mvnw package` e copiar o `.jar` gerado.

## Repositórios relacionados

- [cnpj_interface](https://github.com/antoniorosasse/cnpj_interface)
- [menu_interface](https://github.com/antoniorosasse/menu_interface)
- [ProjetoCargaDados](https://github.com/antoniorosasse/ProjetoCargaDados)
