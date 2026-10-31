# Regras do projeto as400_interface

Este arquivo e lido automaticamente pelo Cline no inicio de **toda** conversa
neste workspace. Mantenha-o enxuto e versionado no git.

## Onde esta o que

| Assunto | Arquivo |
|---|---|
| Regras globais (valem nos 4 projetos: menu, as400, cnpj, carga) | `~/Documentos/Cline/Rules/00-sistema-arosasse.md` |
| Estado atual, pendencias, decisoes e arquitetura | `/home/neto/Projetos/docs/PROJETOS.md` (secao 7.3) |
| Comandos (dev/prod, curl de paginacao, health) | `/home/neto/Projetos/docs/COMANDOS.md` |
| Historico detalhado (blocos 1-32) | `/home/neto/Projetos/docs/HISTORICO.md` |
| Briefing portatil (para outra IA) | `/home/neto/Projetos/docs/TODOS_PROJETOS.md` |

## Idioma e estilo

- Responda sempre em **portugues do Brasil (pt-BR)**.
- Codigo, comentarios e docstrings: **sem acentos**. Prosa em .md com acentos.
- Nao traduza nomes de tabela/coluna do DB2 (`PESSOAS`, `CEPSGEN`,
  `id_pessoa`, `nm_pessoa`) nem nomes de projeto.
- Siga o estilo dos arquivos vizinhos (4 espacos, aspas simples).

## Stack e arquitetura

- Django **6.0.7** (`requirements.txt`), Python 3.13, venv **`env_django`**
  (nao e `venv`). SQLite (`db.sqlite3`) **so** para o admin.
- Pacote Django: **`as400_project/`**; app unico **`pessoas/`**.
- Dados de negocio ficam **no DB2 do IBM i remoto** (pub400), biblioteca
  `AROSASSE1`: `PESSOAS` (500.000 linhas, IDs 1.770.681-2.270.680) e `CEPSGEN`.
- Sem ORM para o DB2: `as400_conn.py` sobe a JVM via JPype e abre
  `jdbc:as400://<host>;libraries=<lib>;naming=sql` com `lib/jt400.jar`;
  consultas usam `prepareStatement` (anti-injecao) e `result_set_generator()`
  para streamar o `ResultSet` em lotes.
- `pool.py`: **conexao unica** global (`pool = ConnectionPool(max_age=300)`),
  validada com `conn.isValid(2)` antes de cada uso; se falhar, recria.
- `views.py` (~1.088 linhas, 14 views): lista paginada, detalhe, novo/editar/
  excluir, `exportar_csv`, `api_pessoas`, CEP (`buscar-cep`, `lista-ceps`),
  `exibir_estabelecimento`, `chat_pessoas`, `testar_deepseek`, `health_deep`.
- Chat: `chat.py` (SDK `openai` -> `api.deepseek.com`) + `contexto.py`
  (historico `max_historico=5` em dict **em memoria**; nao persiste).
- Paginacao: `page=N` (OFFSET, para saltar) e `ultimo_id=` (keyset, no
  "Proxima"). Com 500k linhas o OFFSET grande custa 2-3s.
- Cache: `LocMemCache` (300s) + `@cache_page` em `listar_pessoas` (2 min),
  `pessoas_paginadas` (5 min) e `api_pessoas` (10 min).

## Comandos do projeto

    source env_django/bin/activate
    python manage.py runserver 8001          # http://localhost:8001/
    python manage.py test pessoas            # 5 testes de CSV, sem AS400
    python manage.py check
    time curl -s http://localhost:8001/health/deep/   # 2x: frio ~3-5s, quente ~1,4s

- Use sempre o Python do `env_django/`. Nunca instale pacotes globalmente e nao
  altere `requirements.txt` sem pedir.
- Producao: `cd ~/Projetos && ./deploy.sh as400` (pedir confirmacao).

## Regras de seguranca

- A conexao do app com o pub400 e **read-only na pratica**: a cota e de ~140 MB.
  Nunca rodar DDL (`CREATE`/`ALTER`/`DROP`) nem `DELETE`/`UPDATE` em massa.
- Nunca commitar `.env` nem `lib/jt400.jar`.
- O app e **publico, sem login** (decisao de portfolio): nao expor CPF completo,
  telefone ou e-mail em listagem/tabela — apenas no detalhe, como ja e hoje.
- Proibido criar arquivos de backup manuais (`*.bak`) no repo.

## Convencoes de implementacao

- CSV: sempre `csv.writer` (quoting obrigatorio — enderecos tem virgula),
  `lineterminator='\n'`, utf-8 **no gerador** (`csv_bytes()`) porque
  `StreamingHttpResponse` no Django 6.0 recebe `Iterable[bytes]`. `rs`/`pstmt`
  fecham em `finally` (`_fechar_recursos`) — inclusive quando o download e
  abortado, senao o cursor preso na conexao unica vira `Cursor state not valid`
  (fechado em 31/10; coberto por `test_download_abortado_*` e
  `test_erro_na_query_principal_*`).

- `exibir_estabelecimento` existe **uma vez so** (a duplicata foi removida em
  31/10); nao reintroduzir helpers duplicados em `views.py`.
- Testes novos de view/CSV devem usar dubles de `Connection`/
  `PreparedStatement`/`ResultSet` (padrao de `pessoas/tests.py`), sem tocar o
  AS400.
- Antes de finalizar: `python manage.py test pessoas` + `python manage.py check`
  e relate o resultado.
