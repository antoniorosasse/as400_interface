# pessoas/chat.py
import json
import re
import logging
from django.conf import settings
from .pool import pool
from .contexto import get_conversa, limpar_conversa

# Importar a nova API da OpenAI
from openai import OpenAI

logger = logging.getLogger(__name__)

# Configurar o cliente OpenAI
client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",
)


def processar_pergunta(pergunta_usuario, session_id=None):
    """
    Processa uma pergunta do usuário mantendo contexto da conversa.
    """
    logger.info(f"📝 Pergunta recebida: {pergunta_usuario}")
    
    # Obter conversa da sessão
    if session_id:
        conversa = get_conversa(session_id)
        contexto = conversa.get_contexto()
        historico = conversa.get_historico_texto()
    else:
        conversa = None
        contexto = {}
        historico = ""
    
    try:
        # Passo 1: Gerar SQL com contexto
        logger.info("🔄 Gerando SQL com contexto...")
        sql = gerar_sql_com_contexto(pergunta_usuario, contexto, historico)
        
        if not sql:
            logger.warning("⚠️ SQL não gerado - tentando fallback")
            return processar_pergunta_direta(pergunta_usuario)
        
        logger.info(f"✅ SQL gerado: {sql}")
        
        # Passo 2: EXECUTAR A CONSULTA NO AS/400
        logger.info("🔄 Executando SQL no AS/400...")
        resultado = executar_sql(sql)
        
        if "erro" in resultado:
            logger.error(f"❌ Erro ao executar SQL: {resultado['erro']}")
            return processar_pergunta_direta(pergunta_usuario)
        
        total_registros = len(resultado["dados"])
        logger.info(f"✅ SQL executado - {total_registros} registros encontrados")
        
        # Passo 3: Se não houver dados, informar
        if not resultado["dados"]:
            resposta = f"Não encontrei nenhum registro para sua pergunta."
            return {
                "success": True,
                "resposta": resposta,
                "sql": sql,
                "quantidade": 0
            }
        
        # Passo 4: GERAR RESPOSTA COM OS DADOS REAIS
        logger.info("🔄 Gerando resposta com os dados...")
        resposta = gerar_resposta_com_dados(
            pergunta_usuario, 
            resultado["dados"], 
            sql,
            contexto,
            historico
        )
        
        # Salvar no histórico
        if conversa:
            conversa.adicionar_interacao(pergunta_usuario, resposta, sql)
        
        return {
            "success": True,
            "resposta": resposta,
            "sql": sql,
            "quantidade": total_registros,  # <-- AGORA USA O TOTAL REAL
            "total_dados": total_registros   # <-- ADICIONADO PARA CLAREZA
        }
        
    except Exception as e:
        logger.error(f"❌ Erro no chat: {e}", exc_info=True)
        return {
            "success": False,
            "erro": f"Erro: {str(e)}"
        }


def gerar_sql_com_contexto(pergunta, contexto, historico):
    """
    Gera SQL considerando o contexto da conversa.
    """
    # Construir contexto textual
    contexto_texto = ""
    if contexto:
        contexto_texto = "\nContexto da conversa anterior:\n"
        if 'cidade' in contexto:
            contexto_texto += f"- Cidade mencionada: {contexto['cidade']}\n"
        if 'estado' in contexto:
            contexto_texto += f"- Estado mencionado: {contexto['estado']}\n"
        if 'status' in contexto:
            contexto_texto += f"- Status mencionado: {'Ativo' if contexto['status'] == 'A' else 'Inativo'}\n"
    
    prompt = f"""
    Você é um especialista em SQL para DB2 (AS/400 IBM i).
    
    TABELAS DISPONÍVEIS:
    
    1. AROSASSE1.PESSOAS - Tabela de pessoas/clientes
    CAMPOS:
    - ID_PESSOA (INTEGER) - Identificador único
    - CPF (CHAR(11)) - CPF do cliente
    - NOMECOMPL (VARCHAR(100)) - Nome completo
    - EMAIL (VARCHAR(100)) - Email
    - TELEFONE (VARCHAR(15)) - Telefone
    - DATA_NASC (DATE) - Data de nascimento
    - STATUS (CHAR(1)) - 'A' = Ativo, 'I' = Inativo
    - CEP (CHAR(8)) - CEP (apenas números)
    - ESTADO (CHAR(2)) - UF (ex: SP, RJ, PR)
    - CIDADE (VARCHAR(50)) - Cidade
    - BAIRRO (VARCHAR(50)) - Bairro
    - ENDERECO (VARCHAR(100)) - Endereço
    - NUMERO (VARCHAR(10)) - Número
    - COMPL00001 (VARCHAR(50)) - Complemento
    - DATACADAST (TIMESTAMP) - Data de cadastro

    2. AROSASSE1.CEPSGEN - Tabela de CEPs com informações de endereço
    CAMPOS:
    - CEP (NUMERIC(8,0)) - CEP (apenas números, chave primária)
    - LOGRADOURO (CHAR(78)) - Nome do logradouro (rua, avenida, etc.)
    - LOCALIDADE (CHAR(60)) - Bairro ou localidade
    - ID_MU00001 (CHAR(31)) - ID do município (código IBGE)
    - NOME_00001 (CHAR(32)) - Nome do município (cidade)
    - SIGLA_UF (CHAR(5)) - UF (ex: SP, RJ, PR, SC)
    - ESTAB00001 (CLOB) - Estabelecimentos (texto longo com informações detalhadas)
    - CENTROIDE (CHAR(46)) - Coordenadas geográficas

    {historico}
    {contexto_texto}
    
    REGRAS IMPORTANTES PARA COMPARAÇÃO DE TEXTOS:
    1. Os dados no banco NÃO têm acentos (ex: "Boqueirao", "Sao Paulo")
    2. NUNCA use acentos nas comparações (ex: use "BOQUEIRAO", não "BOQUEIRÃO")
    3. SEMPRE use UPPER() para comparações de texto
    
    EXEMPLO CORRETO: WHERE UPPER(BAIRRO) = UPPER('BOQUEIRAO')
    EXEMPLO ERRADO: WHERE UPPER(BAIRRO) = UPPER('BOQUEIRÃO')  -- NÃO USE ACENTOS!

    REGRAS GERAIS:
    1. Use UPPER() para comparações de texto
    2. Use LIKE para buscas parciais
    3. Use COUNT(*) para contagens
    4. Use DISTINCT para listar valores únicos
    5. Use FETCH FIRST 500 ROWS ONLY para limitar resultados
    6. Para status, use 'A' para ativo e 'I' para inativo
    7. Se não houver filtro de status, NÃO adicione STATUS no WHERE
    8. CEP na tabela PESSOAS é CHAR(8) e na CEPSGEN é NUMERIC(8,0) - compare como string

    EXEMPLOS DE PERGUNTAS E SQL:
    
    Pergunta: "Liste todas as cidades diferentes"
    SQL: SELECT DISTINCT CIDADE FROM AROSASSE1.PESSOAS ORDER BY CIDADE FETCH FIRST 500 ROWS ONLY
    
    Pergunta: "Quantas pessoas estão ativas?"
    SQL: SELECT COUNT(*) AS TOTAL FROM AROSASSE1.PESSOAS WHERE STATUS = 'A'
    
    Pergunta: "Liste os clientes de São Paulo"
    SQL: SELECT * FROM AROSASSE1.PESSOAS WHERE UPPER(CIDADE) = UPPER('SAO PAULO') FETCH FIRST 500 ROWS ONLY
    
    Pergunta: "Liste os bairros de Curitiba e a quantidade de clientes em cada um"
    SQL: SELECT BAIRRO, COUNT(*) AS QTD FROM AROSASSE1.PESSOAS WHERE UPPER(CIDADE) = UPPER('CURITIBA') GROUP BY BAIRRO ORDER BY QTD DESC FETCH FIRST 500 ROWS ONLY
    
    Pergunta: "Mostre o logradouro e cidade para o CEP 12345678"
    SQL: SELECT LOGRADOURO, NOME_00001 AS CIDADE, SIGLA_UF FROM AROSASSE1.CEPSGEN WHERE CEP = 12345678
    
    Pergunta: "Liste todos os CEPs da cidade de Curitiba"
    SQL: SELECT CEP, LOGRADOURO, LOCALIDADE FROM AROSASSE1.CEPSGEN WHERE UPPER(NOME_00001) = UPPER('CURITIBA') FETCH FIRST 500 ROWS ONLY
    
    Pergunta: "Mostre os clientes e seus logradouros a partir do CEP"
    SQL: SELECT P.NOMECOMPL, P.CEP, C.LOGRADOURO, C.NOME_00001 AS CIDADE 
         FROM AROSASSE1.PESSOAS P 
         LEFT JOIN AROSASSE1.CEPSGEN C ON P.CEP = CAST(C.CEP AS CHAR(8))
         WHERE P.CEP IS NOT NULL FETCH FIRST 500 ROWS ONLY

    AGORA, converta a seguinte pergunta para SQL:
    "{pergunta}"
    
    IMPORTANTE: 
    - Retorne APENAS o SQL, sem explicações.
    - Use os nomes completos das tabelas: AROSASSE1.PESSOAS e AROSASSE1.CEPSGEN
    - NUNCA use acentos nas comparações
    - Use FETCH FIRST 500 ROWS ONLY para listagens
    - Se a pergunta envolver CEP, considere usar a tabela CEPSGEN
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um especialista em SQL para DB2/AS400. As tabelas são AROSASSE1.PESSOAS e AROSASSE1.CEPSGEN. NUNCA use acentos. Use FETCH FIRST 500 ROWS ONLY. Retorne apenas o SQL."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        sql = response.choices[0].message.content.strip()
        
        # Limpar o SQL
        sql = re.sub(r'```sql\n?', '', sql)
        sql = re.sub(r'```\n?', '', sql)
        sql = sql.strip()
        
        # Verificar se é um SELECT
        if not sql.upper().startswith('SELECT'):
            logger.warning(f"⚠️ SQL não é SELECT: {sql[:100]}")
            return None
            
        return sql
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar SQL: {e}", exc_info=True)
        return None


def gerar_resposta_com_contexto(pergunta, dados, sql, contexto, historico):
    """
    Gera resposta considerando o contexto.
    """
    if not dados:
        return "Não encontrei nenhum registro que corresponda à sua pergunta. Tente refinar sua busca."
    
    dados_formatados = json.dumps(dados, ensure_ascii=False, indent=2)
    
    prompt = f"""
    Pergunta do usuário: "{pergunta}"
    
    Contexto anterior:
    {historico}
    
    Contexto extraído:
    {json.dumps(contexto, ensure_ascii=False, indent=2)}
    
    Resultado da consulta SQL:
    {dados_formatados}
    
    Com base nestes dados, responda à pergunta do usuário de forma clara, amigável e objetiva.
    MANTENHA O CONTEXTO DA CONVERSA! Se o usuário pediu para dividir por bairro e a cidade já foi mencionada, 
    responda sobre os bairros daquela cidade específica.
    Se houver muitos dados, faça um resumo e destaque os mais importantes.
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em dados de clientes. Mantenha o contexto da conversa."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {e}")
        return f"Encontrei {len(dados)} registro(s) para sua pergunta. Verifique os detalhes no sistema."


def gerar_sql(pergunta):
    """
    Usa a DeepSeek para converter pergunta em SQL para DB2/AS400.
    """
    logger.info(f"🔄 Chamando DeepSeek para gerar SQL da pergunta: {pergunta[:50]}...")
    
    try:
        # Testar se a API key está configurada
        if not settings.DEEPSEEK_API_KEY:
            logger.error("❌ DEEPSEEK_API_KEY não configurada!")
            return None
            
        prompt = f"""
        Você é um especialista em SQL para DB2 (AS/400 IBM i).
        
        TABELA: AROSASSE1.PESSOAS
        CAMPOS:
        - ID_PESSOA (INTEGER) - Identificador único
        - CPF (CHAR(11)) - CPF do cliente (apenas números)
        - NOMECOMPL (VARCHAR(100)) - Nome completo
        - EMAIL (VARCHAR(100)) - Email
        - TELEFONE (VARCHAR(15)) - Telefone
        - DATA_NASC (DATE) - Data de nascimento (formato YYYY-MM-DD)
        - STATUS (CHAR(1)) - 'A' = Ativo, 'I' = Inativo
        - CEP (CHAR(8)) - CEP (apenas números)
        - ESTADO (CHAR(2)) - UF (ex: SP, RJ, MG)
        - CIDADE (VARCHAR(50)) - Cidade
        - BAIRRO (VARCHAR(50)) - Bairro
        - ENDERECO (VARCHAR(100)) - Endereço
        - NUMERO (VARCHAR(10)) - Número
        - COMPL00001 (VARCHAR(50)) - Complemento
        - DATACADAST (TIMESTAMP) - Data de cadastro

        REGRAS IMPORTANTES:
        1. Use UPPER() para comparações de texto
        2. Use LIKE para buscas parciais
        3. Use COUNT(*) para contagens
        4. Use FETCH FIRST N ROWS ONLY para limitar resultados (máximo 100)
        5. Use DATE('YYYY-MM-DD') para datas
        6. Para status, use 'A' para ativo e 'I' para inativo

        EXEMPLOS:
        Pergunta: "Quantas pessoas estão ativas?"
        SQL: SELECT COUNT(*) AS TOTAL FROM AROSASSE1.PESSOAS WHERE STATUS = 'A'
        
        Pergunta: "Liste os 5 clientes mais recentes"
        SQL: SELECT ID_PESSOA, NOMECOMPL FROM AROSASSE1.PESSOAS ORDER BY DATACADAST DESC FETCH FIRST 5 ROWS ONLY

        AGORA, converta a seguinte pergunta para SQL:
        "{pergunta}"
        
        Retorne APENAS o SQL, sem explicações.
        """
        
        logger.info("🔄 Enviando requisição para DeepSeek (nova API)...")
        
        # Usar a nova sintaxe: client.chat.completions.create
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um especialista em SQL. Retorne apenas o SQL."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=300
        )
        
        # Extrair o conteúdo da resposta (nova sintaxe)
        sql = response.choices[0].message.content.strip()
        logger.info(f"✅ Resposta recebida da DeepSeek: {sql[:100]}...")
        
        # Limpar o SQL
        sql = re.sub(r'```sql\n?', '', sql)
        sql = re.sub(r'```\n?', '', sql)
        sql = sql.strip()
        
        # Verificar se é um SELECT
        if not sql.upper().startswith('SELECT'):
            logger.warning(f"⚠️ SQL não é SELECT: {sql[:100]}")
            return None
            
        return sql
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar SQL: {e}", exc_info=True)
        return None


def executar_sql(sql):
    """
    Executa uma consulta SQL no AS/400 e retorna os dados.
    """
    try:
        conn = pool.get_connection()
        stmt = conn.createStatement()
        stmt.setFetchSize(2000)  # Aumentar fetch size para 2000
        
        # Limitar número de resultados para segurança
        # ALTERADO: Agora usa 500 registros
        if 'FETCH FIRST' not in sql.upper() and 'COUNT' not in sql.upper():
            sql = sql.rstrip(';') + " FETCH FIRST 500 ROWS ONLY"
        
        logger.info(f"📊 Executando SQL: {sql[:200]}...")
        
        rs = stmt.executeQuery(sql)
        
        # Obter metadados
        meta = rs.getMetaData()
        num_colunas = meta.getColumnCount()
        colunas = [str(meta.getColumnLabel(i + 1)) for i in range(num_colunas)]
        
        # Extrair dados
        dados = []
        while rs.next():
            linha = {}
            for i, nome_col in enumerate(colunas, start=1):
                valor = rs.getString(i)
                linha[nome_col] = str(valor) if valor is not None else ''
            dados.append(linha)
        
        rs.close()
        stmt.close()
        
        logger.info(f"✅ {len(dados)} registros encontrados")
        
        return {"dados": dados}
        
    except Exception as e:
        logger.error(f"Erro ao executar SQL: {e}")
        return {"erro": str(e)}


def gerar_resposta(pergunta, dados, sql):
    """
    Usa a DeepSeek para transformar os dados em uma resposta amigável.
    """
    if not dados:
        return "Não encontrei nenhum registro que corresponda à sua pergunta. Tente refinar sua busca."
    
    dados_formatados = json.dumps(dados, ensure_ascii=False, indent=2)
    
    prompt = f"""
    Pergunta do usuário: "{pergunta}"
    
    Resultado da consulta SQL:
    {dados_formatados}
    
    Com base nestes dados, responda à pergunta do usuário de forma clara, amigável e objetiva.
    Se houver muitos dados, faça um resumo e destaque os mais importantes.
    Use uma linguagem natural e profissional.
    """
    
    try:
        # Usar a nova sintaxe
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em dados de clientes. Responda de forma clara e profissional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {e}")
        return f"Encontrei {len(dados)} registro(s) para sua pergunta. Verifique os detalhes no sistema."


def processar_pergunta_direta(pergunta_usuario):
    """
    Fallback: quando não consegue gerar SQL, tenta responder diretamente com a IA.
    """
    try:
        prompt = f"""
        As tabelas disponíveis são:
        
        1. AROSASSE1.PESSOAS com campos:
        ID_PESSOA, CPF, NOMECOMPL, EMAIL, TELEFONE, DATA_NASC, STATUS, 
        CEP, ESTADO, CIDADE, BAIRRO, ENDERECO, NUMERO, COMPL00001, DATACADAST
        
        2. AROSASSE1.CEPSGEN com campos:
        CEP, LOGRADOURO, LOCALIDADE, ID_MU00001, NOME_00001, SIGLA_UF, ESTAB00001, CENTROIDE
        
        O usuário perguntou: "{pergunta_usuario}"
        
        Converta esta pergunta em SQL para as tabelas acima.
        Retorne APENAS o SQL, sem explicações.
        
        Exemplos:
        - "Liste todas as cidades diferentes" → SELECT DISTINCT CIDADE FROM AROSASSE1.PESSOAS ORDER BY CIDADE
        - "Quantas pessoas estão ativas?" → SELECT COUNT(*) FROM AROSASSE1.PESSOAS WHERE STATUS = 'A'
        - "Mostre o logradouro para o CEP 12345678" → SELECT LOGRADOURO FROM AROSASSE1.CEPSGEN WHERE CEP = 12345678
        """
        
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um especialista em SQL. As tabelas são AROSASSE1.PESSOAS e AROSASSE1.CEPSGEN. Retorne apenas o SQL."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=400
        )
        
        sql = response.choices[0].message.content.strip()
        
        # Tentar executar o SQL
        resultado = executar_sql(sql)
        
        if "erro" not in resultado and resultado["dados"]:
            return {
                "success": True,
                "resposta": f"Resultado da consulta:\n\n{json.dumps(resultado['dados'], ensure_ascii=False, indent=2)}\n\nSQL executado:\n{sql}",
                "sql": sql,
                "quantidade": len(resultado["dados"])
            }
        else:
            return {
                "success": False,
                "erro": "Não foi possível processar sua pergunta. Tente reformular."
            }
        
    except Exception as e:
        logger.error(f"Erro no fallback: {e}")
        return {
            "success": False,
            "erro": "Não foi possível processar sua pergunta. Tente reformular."
        }
    
def gerar_resposta_com_dados(pergunta, dados, sql, contexto, historico):
    """
    Gera resposta com os dados reais da consulta.
    """
    if not dados:
        return "Não encontrei nenhum registro que corresponda à sua pergunta."
    
    # Extrair informações para o prompt
    total_registros = len(dados)
    
    # Formatar dados para exibição (apenas os primeiros para não sobrecarregar)
    dados_para_mostrar = dados[:50]  # Limitar a 50 para não estourar o token
    dados_formatados = json.dumps(dados_para_mostrar, ensure_ascii=False, indent=2)
    
    # Calcular totais reais dos dados
    total_pessoas = 0
    if dados and 'QTD_PESSOAS' in dados[0]:
        for item in dados:
            try:
                total_pessoas += int(item.get('QTD_PESSOAS', 0))
            except:
                pass
    
    prompt = f"""
    Você é um assistente especializado em análise de dados.

    DADOS REAIS OBTIDOS DA CONSULTA (NÃO INVENTE NÚMEROS):
    Total de registros retornados: {total_registros}
    Total de pessoas somado: {total_pessoas if total_pessoas > 0 else 'N/A'}
    
    Dados (JSON):
    {dados_formatados}

    Pergunta do usuário: "{pergunta}"

    INSTRUÇÕES OBRIGATÓRIAS:
    1. Use APENAS os dados fornecidos acima
    2. NUNCA invente números ou totais que não estão nos dados
    3. Se não souber um número, diga que não está disponível
    4. Apresente os dados de forma clara e organizada
    5. Se for uma lista, use marcadores ou tabela
    6. Se for uma contagem, use o número exato dos dados
    
    IMPORTANTE: Você tem {total_registros} registros. Use APENAS esses dados!
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um analista de dados. Use APENAS os dados fornecidos. NUNCA invente números ou totais."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Baixa temperatura para ser mais preciso
            max_tokens=1000
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {e}")
        # Fallback: mostrar os dados em formato simples
        return f"Resultado da consulta ({total_registros} registros):\n\n{json.dumps(dados, ensure_ascii=False, indent=2)}"

    