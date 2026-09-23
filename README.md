# AS/400 Interface

Interface web para consulta e CRUD de pessoas no AS/400 (IBM i), com
integracao a PostgreSQL e MongoDB. Inclui um chat IA que traduz perguntas
em linguagem natural para SQL.

Este repositorio contem **duas partes**:

1. **Aplicacao Django** (raiz do repo) - interface web
2. **API Java Spring Boot** (`ceps-api/`) - gerador de aplicacao para rodar no AS/400

## Stack

### Django (raiz)

- Django 6.0.7
- Python 3.13
- JPype + jt400.jar (conexao JDBC com AS/400)
- PostgreSQL (psycopg2-binary)
- MongoDB (pymongo)
- DeepSeek (chat IA via openai SDK)
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
    |   +-- pool.py                 # Pool de conexoes
    |   +-- ceps.py                 # Busca de CEP
    |   +-- chat.py                 # Pipeline do chat IA
    |   +-- contexto.py             # Contexto da conversa
    |   +-- validators.py           # Validacao de CPF, email, etc
    |   +-- views.py                # Views (1051 linhas)
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
| GET | `/health/` | Health check |

## Chat IA

O chat usa o pipeline:

    Pergunta -> gerar_sql -> executar_sql -> gerar_resposta

- `pessoas/chat.py` - pipeline principal
- `pessoas/contexto.py` - mantem contexto da conversa (ultimas 5 interacoes)
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

O `ceps-api/` e um projeto Java Spring Boot que gera uma aplicacao para
rodar **dentro** do AS/400. Ele nao e chamado pela aplicacao Django em
runtime - e uma ferramenta separada, mantida no mesmo repositorio por
conveniencia.

## Repositorios relacionados

- [cnpj_interface](https://github.com/antoniorosasse/cnpj_interface)
- [menu_interface](https://github.com/antoniorosasse/menu_interface)
- [ProjetoCargaDados](https://github.com/antoniorosasse/ProjetoCargaDados)
- [Projetos](https://github.com/antoniorosasse/Projetos) - scripts e manual de git
