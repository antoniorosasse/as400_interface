import time
#inicio = time.time()
import re
import csv
from io import StringIO
from django.http import StreamingHttpResponse
from datetime import date, datetime
import jpype
from django.http import JsonResponse

from django.shortcuts import render, redirect
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.vary import vary_on_headers
from django.core.cache import cache
from .pool import pool
from .validators import limpar_telefone, limpar_cep, limpar_estado, validar_cpf, validar_email
from django.core.exceptions import ValidationError
from .validators import validar_cep_existe
from django.http import JsonResponse
from .ceps import buscar_cep



# ==================== GERADOR ====================
from datetime import date, datetime  # Certifique-se de que está no topo do arquivo

def result_set_generator(rs):
    """
    Converte um ResultSet JDBC em um gerador de dicionários Python.
    - Converte java.lang.String para str nativa
    - DATA_NASC: converte para date (trata anos com 2 dígitos)
    - DATACADAST: converte para datetime
    """
    meta = rs.getMetaData()
    num_colunas = meta.getColumnCount()
    colunas = [str(meta.getColumnLabel(i + 1)) for i in range(num_colunas)]

    while rs.next():
        linha = {}
        for i, nome_col in enumerate(colunas, start=1):
            valor = rs.getString(i)

            if valor is not None:
                # ----- CONVERTE JAVA.STRING PARA STR NATIVA -----
                valor_str = str(valor)   # <-- ESSA LINHA RESOLVE O ERRO
                nome_lower = nome_col.lower()

                # --- DATA_NASC (DATE) ---
                if nome_lower == 'data_nasc':
                    try:
                        # Se tiver formato 'YY-MM-DD' (ex: '65-08-04')
                        if len(valor_str) == 8 and valor_str[2] == '-' and valor_str[5] == '-':
                            ano = int(valor_str[:2])
                            if ano > 50:
                                valor_corrigido = f"19{valor_str}"
                            else:
                                valor_corrigido = f"20{valor_str}"
                            linha[nome_lower] = datetime.strptime(valor_corrigido, '%Y-%m-%d').date()
                        else:
                            # Tenta formato padrão YYYY-MM-DD
                            linha[nome_lower] = datetime.strptime(valor_str, '%Y-%m-%d').date()
                    except Exception as e:
                        print(f"Erro ao converter DATA_NASC: {valor_str} -> {e}")
                        linha[nome_lower] = valor_str  # fallback

                # --- DATACADAST (TIMESTAMP) ---
                elif nome_lower == 'datacadast':
                    try:
                        linha[nome_lower] = datetime.strptime(valor_str, '%Y-%m-%d %H:%M:%S.%f')
                    except Exception as e:
                        print(f"Erro ao converter DATACADAST: {valor_str} -> {e}")
                        linha[nome_lower] = valor_str  # fallback

                # --- DEMAIS CAMPOS ---
                else:
                    linha[nome_lower] = valor_str

            else:
                linha[nome_lower] = None

        yield linha

# ==================== LISTAGEM LIMITADA ====================
@cache_page(60 * 2)
@never_cache
def listar_pessoas(request):
    try:
        conn = pool.get_connection()
        stmt = conn.createStatement()
        stmt.setFetchSize(2000)

        rs_count = stmt.executeQuery("SELECT COUNT(*) FROM AROSASSE1.PESSOAS")
        rs_count.next()
        total = rs_count.getInt(1)
        rs_count.close()

        sql = "SELECT * FROM AROSASSE1.PESSOAS ORDER BY ID_PESSOA FETCH FIRST 1000 ROWS ONLY"
        rs = stmt.executeQuery(sql)
        pessoas = list(result_set_generator(rs))
        rs.close()

        context = {
            'pessoas': pessoas,
            'total': total,
            'limitado': True,
            'mostrados': len(pessoas),
        }
        return render(request, 'pessoas/lista.html', context)
    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})

# ==================== PAGINAÇÃO COM FILTROS ====================
@cache_page(60 * 5)
@vary_on_headers('Accept-Encoding')
@never_cache
def pessoas_paginadas(request):
    try:
        # Parâmetros
        page = int(request.GET.get('page', 1))
        size = int(request.GET.get('size', 10))
        nome = request.GET.get('nome', '').strip()
        cpf = request.GET.get('cpf', '').strip()
        status = request.GET.get('status', '').strip()
        estado = request.GET.get('estado', '').strip()
        cep = request.GET.get('cep', '').strip()
        data_nasc_inicio = request.GET.get('data_nasc_inicio', '').strip()
        data_nasc_fim = request.GET.get('data_nasc_fim', '').strip()
        ordering = request.GET.get('ordering', 'id_pessoa').strip()
        order = request.GET.get('order', 'asc').strip()

        # Keyset
        ultimo_id = request.GET.get('ultimo_id')
        if ultimo_id:
            ultimo_id = int(ultimo_id)
        else:
            ultimo_id = 0

        # Validações
        if page < 1: page = 1
        if size < 1: size = 10
        if size > 100: size = 100
        if order not in ['asc', 'desc']: order = 'asc'
        colunas_validas = ['id_pessoa', 'cpf', 'nomecompl', 'email', 'telefone', 'data_nasc', 'status', 'cep', 'estado']
        if ordering.lower() not in colunas_validas:
            ordering = 'id_pessoa'
        coluna_db = {
            'id_pessoa': 'ID_PESSOA', 'cpf': 'CPF', 'nomecompl': 'NOMECOMPL',
            'email': 'EMAIL', 'telefone': 'TELEFONE', 'data_nasc': 'DATA_NASC',
            'status': 'STATUS', 'cep': 'CEP', 'estado': 'ESTADO'
        }[ordering.lower()]

        conn = pool.get_connection()
        stmt = conn.createStatement()
        stmt.setFetchSize(2000)

        # ---------- WHERE (filtros) ----------
        where_parts = []
        params = []
        if nome:
            where_parts.append("UPPER(NOMECOMPL) LIKE ?")
            params.append(f"%{nome.upper()}%")
        if cpf:
            where_parts.append("CPF LIKE ?")
            params.append(f"%{cpf}%")
        if status:
            where_parts.append("STATUS = ?")
            params.append(status)
        if estado:
            where_parts.append("ESTADO = ?")
            params.append(estado)
        if cep:
            where_parts.append("CEP LIKE ?")
            params.append(f"%{cep}%")
        if data_nasc_inicio:
            try:
                dt = datetime.strptime(data_nasc_inicio, '%Y-%m-%d').date()
                where_parts.append("DATA_NASC >= ?")
                params.append(dt)
            except:
                pass
        if data_nasc_fim:
            try:
                dt = datetime.strptime(data_nasc_fim, '%Y-%m-%d').date()
                where_parts.append("DATA_NASC <= ?")
                params.append(dt)
            except:
                pass

        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        # ---------- CACHE DA CONTAGEM ----------
        cache_key = f"total_pessoas_{nome}_{cpf}_{status}_{estado}_{cep}_{data_nasc_inicio}_{data_nasc_fim}"
        total = cache.get(cache_key)
        if total is None:
            count_sql = f"SELECT COUNT(*) FROM AROSASSE1.PESSOAS{where_clause}"
            pstmt_count = conn.prepareStatement(count_sql)
            pstmt_count.setFetchSize(500)
            for i, p in enumerate(params, start=1):
                pstmt_count.setObject(i, p)
            rs_count = pstmt_count.executeQuery()
            rs_count.next()
            total = rs_count.getInt(1)
            rs_count.close()
            pstmt_count.close()
            cache.set(cache_key, total, 60 * 5)

        # ---------- DECISÃO: KEYSET OU OFFSET ----------
        usar_keyset = (not nome) and (ordering == 'id_pessoa')

        if usar_keyset:
            # Monta a cláusula keyset corretamente
            if ultimo_id and ultimo_id > 0:
                if where_clause:
                    keyset_condition = f" AND ID_PESSOA > ?"
                else:
                    keyset_condition = f" WHERE ID_PESSOA > ?"
                params_main = params.copy()
                params_main.append(ultimo_id)
            else:
                keyset_condition = ""
                params_main = params.copy()

            params_main.append(size)  # FETCH FIRST ? ROWS ONLY

            sql = f"""
                SELECT * FROM AROSASSE1.PESSOAS
                {where_clause}
                {keyset_condition}
                ORDER BY ID_PESSOA
                FETCH FIRST ? ROWS ONLY
            """
            pstmt = conn.prepareStatement(sql)
            pstmt.setFetchSize(2000)
            for i, p in enumerate(params_main, start=1):
                pstmt.setObject(i, p)
            rs = pstmt.executeQuery()
        else:
            # OFFSET (com ordenação dinâmica)
            offset = (page - 1) * size
            sql = f"""
                SELECT * FROM AROSASSE1.PESSOAS
                {where_clause}
                ORDER BY {coluna_db} {order}
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """
            params_main = params.copy()
            params_main.append(offset)
            params_main.append(size)
            pstmt = conn.prepareStatement(sql)
            pstmt.setFetchSize(2000)
            for i, p in enumerate(params_main, start=1):
                pstmt.setObject(i, p)
            rs = pstmt.executeQuery()

        pessoas = list(result_set_generator(rs))
        rs.close()
        pstmt.close()
        stmt.close()

        proximo_ultimo_id = pessoas[-1]['id_pessoa'] if pessoas else None
        total_pages = (total + size - 1) // size if size > 0 else 0

        context = {
            'pessoas': pessoas,
            'page': page,
            'size': size,
            'total': total,
            'total_pages': total_pages,
            'nome': nome,
            'cpf': cpf,
            'status': status,
            'estado': estado,
            'cep': cep,
            'data_nasc_inicio': data_nasc_inicio,
            'data_nasc_fim': data_nasc_fim,
            'ordering': ordering,
            'order': order,
            'ultimo_id': ultimo_id,
            'proximo_ultimo_id': proximo_ultimo_id,
            'usando_keyset': usar_keyset,
        }
        return render(request, 'pessoas/lista_paginada.html', context)

    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})

# ==================== EXPORTAÇÃO CSV ====================
def exportar_csv(request):
    nome = request.GET.get('nome', '').strip()
    try:
        conn = pool.get_connection()
        
        # Primeiro, contar total para log
        count_sql = "SELECT COUNT(*) FROM AROSASSE1.PESSOAS" + (" WHERE UPPER(NOMECOMPL) LIKE ?" if nome else "")
        pstmt_count = conn.prepareStatement(count_sql)
        if nome:
            pstmt_count.setString(1, f"%{nome.upper()}%")
        rs_count = pstmt_count.executeQuery()
        rs_count.next()
        total = rs_count.getInt(1)
        rs_count.close()
        pstmt_count.close()
        print(f"📊 Exportando CSV com {total} registros...")

        # Query principal
        sql = "SELECT * FROM AROSASSE1.PESSOAS" + (" WHERE UPPER(NOMECOMPL) LIKE ? ORDER BY ID_PESSOA" if nome else " ORDER BY ID_PESSOA")
        pstmt = conn.prepareStatement(sql)
        pstmt.setFetchSize(2000)  # Busca 500 linhas por vez
        if nome:
            pstmt.setString(1, f"%{nome.upper()}%")
        rs = pstmt.executeQuery()

        # Gerador de linhas CSV (streaming)
        def csv_generator():
            meta = rs.getMetaData()
            num_colunas = meta.getColumnCount()
            cabecalho = [str(meta.getColumnLabel(i + 1)) for i in range(num_colunas)]
            yield cabecalho

            count = 0
            while rs.next():
                linha = []
                for i in range(1, num_colunas + 1):
                    valor = rs.getString(i)
                    linha.append(str(valor) if valor is not None else "")
                yield linha
                count += 1
                if count % 50000 == 0:
                    print(f"   Exportadas {count} linhas...")
            print(f"✅ Total exportado: {count} linhas.")
            rs.close()
            pstmt.close()

        # Criar resposta CSV com streaming
        response = StreamingHttpResponse(
            (','.join(linha) + '\n' for linha in csv_generator()),
            content_type='text/csv;charset=utf-8'
        )
        filename = f"pessoas_{nome if nome else 'todos'}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        print("❌ Erro na exportação:", str(e))
        return render(request, 'pessoas/erro.html', {'erro': str(e)})

# ==================== API JSON ====================
@cache_page(60 * 10)
@never_cache
def api_pessoas(request):
    try:
        conn = pool.get_connection()
        stmt = conn.createStatement()
        stmt.setFetchSize(2000)
        rs = stmt.executeQuery("SELECT ID_PESSOA, CPF, NOMECOMPL, EMAIL FROM AROSASSE1.PESSOAS FETCH FIRST 100 ROWS ONLY")
        data = list(result_set_generator(rs))
        rs.close()
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ==================== DETALHE ====================
@never_cache
def detalhe_pessoa(request, id_pessoa):
    try:
        conn = pool.get_connection()
        pstmt = conn.prepareStatement("SELECT * FROM AROSASSE1.PESSOAS WHERE ID_PESSOA = ?")
        pstmt.setFetchSize(2000)
        pstmt.setInt(1, id_pessoa)
        rs = pstmt.executeQuery()

        if rs.next():
            # --- Extrair metadados ---
            meta = rs.getMetaData()
            num_colunas = meta.getColumnCount()
            pessoa = {}

            for i in range(1, num_colunas + 1):
                nome_col = str(meta.getColumnLabel(i))
                valor = rs.getString(i)

                if valor is not None:
                    valor_str = str(valor)  # converte java.lang.String para str
                    nome_lower = nome_col.lower()

                    # --- DATA_NASC (DATE) ---
                    if nome_lower == 'data_nasc':
                        try:
                            # Trata formato 'YY-MM-DD'
                            if len(valor_str) == 8 and valor_str[2] == '-' and valor_str[5] == '-':
                                ano = int(valor_str[:2])
                                if ano > 50:
                                    valor_corrigido = f"19{valor_str}"
                                else:
                                    valor_corrigido = f"20{valor_str}"
                                pessoa[nome_lower] = datetime.strptime(valor_corrigido, '%Y-%m-%d').date()
                            else:
                                pessoa[nome_lower] = datetime.strptime(valor_str, '%Y-%m-%d').date()
                        except Exception as e:
                            print(f"Erro ao converter DATA_NASC no detalhe: {valor_str} -> {e}")
                            pessoa[nome_lower] = valor_str

                    # --- DATACADAST (TIMESTAMP) ---
                    elif nome_lower == 'datacadast':
                        try:
                            pessoa[nome_lower] = datetime.strptime(valor_str, '%Y-%m-%d %H:%M:%S.%f')
                        except Exception as e:
                            print(f"Erro ao converter DATACADAST no detalhe: {valor_str} -> {e}")
                            pessoa[nome_lower] = valor_str

                    # --- DEMAIS CAMPOS ---
                    else:
                        pessoa[nome_lower] = valor_str
                else:
                    pessoa[nome_lower] = None

            rs.close()
            pstmt.close()
            return render(request, 'pessoas/detalhe.html', {'pessoa': pessoa})

        else:
            rs.close()
            pstmt.close()
            return render(request, 'pessoas/erro.html', {'erro': 'Pessoa não encontrada.'})

    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})

# ==================== CRIAR ====================
def criar_pessoa(request):
    if request.method == 'POST':
        cpf = request.POST.get('cpf', '').strip()
        nomecompl = request.POST.get('nomecompl', '').strip()
        email = request.POST.get('email', '').strip()
        telefone = request.POST.get('telefone', '').strip()
        data_nasc = request.POST.get('data_nasc', '').strip()
        status = request.POST.get('status', 'A').strip()
        cep = request.POST.get('cep', '').strip()
        # Campos que serão preenchidos pelo CEP (mas endereco pode ser editado)
        estado = ''
        cidade = ''
        bairro = ''
        endereco = ''
        numero = request.POST.get('numero', '').strip()
        complemento = request.POST.get('complemento', '').strip()

        # ----- LIMPEZA -----
        cpf = re.sub(r'\D', '', cpf)
        telefone = limpar_telefone(telefone)
        cep = limpar_cep(cep)

        # ----- VALIDAÇÕES DE CAMPOS OBRIGATÓRIOS -----
        if not cpf:
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'CPF é obrigatório.', 'pessoa': request.POST, 'edicao': False})
        if not nomecompl:
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'Nome completo é obrigatório.', 'pessoa': request.POST, 'edicao': False})
        if not telefone:
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'Telefone é obrigatório.', 'pessoa': request.POST, 'edicao': False})
        if not cep:
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'CEP é obrigatório.', 'pessoa': request.POST, 'edicao': False})
        if not data_nasc:
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'Data de Nascimento é obrigatória.', 'pessoa': request.POST, 'edicao': False})
        if not numero:
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'Número é obrigatório.', 'pessoa': request.POST, 'edicao': False})

        # ----- VALIDAÇÕES DE FORMATO -----
        if not validar_cpf(cpf):
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'CPF inválido.', 'pessoa': request.POST, 'edicao': False})
        if email and not validar_email(email):
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'Email inválido.', 'pessoa': request.POST, 'edicao': False})
        if len(cep) != 8:
            return render(request, 'pessoas/form_pessoa.html', {'erro': 'CEP deve ter 8 dígitos.', 'pessoa': request.POST, 'edicao': False})

        # ----- VALIDAÇÃO DO CEP NA TABELA CEPSGEN -----
        from .validators import validar_cep_existe
        try:
            dados_cep = validar_cep_existe(cep)
        except ValidationError as e:
            return render(request, 'pessoas/form_pessoa.html', {'erro': str(e), 'pessoa': request.POST, 'edicao': False})

        # Preencher campos a partir do CEP
        # Endereço: se o usuário já digitou algo, mantém; senão, usa o logradouro
        endereco = request.POST.get('endereco', '').strip()
        if not endereco:
            endereco = dados_cep['logradouro']

        bairro = dados_cep['localidade']      # sempre do CEPSGEN (readonly)
        cidade = dados_cep['nome_municipio']  # sempre do CEPSGEN (readonly)
        estado = dados_cep['sigla_uf']        # sempre do CEPSGEN (readonly)

        # ----- INSERÇÃO -----
        try:
            conn = pool.get_connection()
            java_sql_date = jpype.JClass('java.sql.Date')
            try:
                data_java = java_sql_date.valueOf(data_nasc)
            except:
                hoje = date.today()
                data_java = java_sql_date.valueOf(hoje.isoformat())

            sql = """INSERT INTO AROSASSE1.PESSOAS 
                     (CPF, NOMECOMPL, EMAIL, TELEFONE, DATA_NASC, STATUS, CEP, ESTADO, 
                      CIDADE, BAIRRO, ENDERECO, NUMERO, COMPL00001)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            pstmt = conn.prepareStatement(sql)

            pstmt.setString(1, cpf)
            pstmt.setString(2, nomecompl)
            pstmt.setString(3, email if email else '')
            pstmt.setString(4, telefone)
            pstmt.setDate(5, data_java)
            pstmt.setString(6, status)
            pstmt.setString(7, cep)
            pstmt.setString(8, estado)
            pstmt.setString(9, cidade)
            pstmt.setString(10, bairro)
            pstmt.setString(11, endereco)
            pstmt.setString(12, numero)
            pstmt.setString(13, complemento)

            try:
                pstmt.executeUpdate()
            except Exception as e:
                if 'SQL0803' in str(e):
                    return render(request, 'pessoas/form_pessoa.html', {'erro': 'Este CPF já está cadastrado.', 'pessoa': request.POST, 'edicao': False})
                raise

            pstmt.close()
            cache.clear()
            next_url = request.POST.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('home')

        except Exception as e:
            print(f"ERRO NA INCLUSÃO: {e}")
            return render(request, 'pessoas/form_pessoa.html', {'erro': str(e), 'pessoa': request.POST, 'edicao': False})

    # GET
    next_url = request.GET.get('next', '')
    return render(request, 'pessoas/form_pessoa.html', {'pessoa': None, 'edicao': False, 'next_url': next_url})

# ==================== EDITAR ====================
def editar_pessoa(request, id_pessoa):
    try:
        conn = pool.get_connection()
        if request.method == 'POST':
            cpf = request.POST.get('cpf', '').strip()
            nomecompl = request.POST.get('nomecompl', '').strip()
            email = request.POST.get('email', '').strip()
            telefone = request.POST.get('telefone', '').strip()
            data_nasc = request.POST.get('data_nasc', '').strip()
            status = request.POST.get('status', 'A').strip()
            cep = request.POST.get('cep', '').strip()
            # Campos que serão preenchidos pelo CEP (endereco pode ser editado)
            estado = ''
            cidade = ''
            bairro = ''
            endereco = ''
            numero = request.POST.get('numero', '').strip()
            complemento = request.POST.get('complemento', '').strip()

            # ----- LIMPEZA -----
            cpf = re.sub(r'\D', '', cpf)
            telefone = limpar_telefone(telefone)
            cep = limpar_cep(cep)

            # ----- VALIDAÇÕES DE CAMPOS OBRIGATÓRIOS -----
            if not cpf:
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'CPF é obrigatório.', 'pessoa': request.POST, 'edicao': True})
            if not nomecompl:
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'Nome completo é obrigatório.', 'pessoa': request.POST, 'edicao': True})
            if not telefone:
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'Telefone é obrigatório.', 'pessoa': request.POST, 'edicao': True})
            if not cep:
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'CEP é obrigatório.', 'pessoa': request.POST, 'edicao': True})
            if not data_nasc:
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'Data de Nascimento é obrigatória.', 'pessoa': request.POST, 'edicao': True})
            if not numero:
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'Número é obrigatório.', 'pessoa': request.POST, 'edicao': True})

            # ----- VALIDAÇÕES DE FORMATO -----
            if not validar_cpf(cpf):
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'CPF inválido.', 'pessoa': request.POST, 'edicao': True})
            if email and not validar_email(email):
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'Email inválido.', 'pessoa': request.POST, 'edicao': True})
            if len(cep) != 8:
                return render(request, 'pessoas/form_pessoa.html', {'erro': 'CEP deve ter 8 dígitos.', 'pessoa': request.POST, 'edicao': True})

            # ----- VALIDAÇÃO DO CEP NA TABELA CEPSGEN -----
            from .validators import validar_cep_existe
            try:
                dados_cep = validar_cep_existe(cep)
            except ValidationError as e:
                return render(request, 'pessoas/form_pessoa.html', {'erro': str(e), 'pessoa': request.POST, 'edicao': True})

            # Preencher campos a partir do CEP (endereco mantém o que o usuário digitou)
            endereco = request.POST.get('endereco', '').strip()
            if not endereco:
                endereco = dados_cep['logradouro']

            bairro = dados_cep['localidade']      # sempre do CEPSGEN (readonly)
            cidade = dados_cep['nome_municipio']  # sempre do CEPSGEN (readonly)
            estado = dados_cep['sigla_uf']        # sempre do CEPSGEN (readonly)

            # ----- TRATAMENTO DA DATA -----
            java_sql_date = jpype.JClass('java.sql.Date')

            def obter_data_original():
                try:
                    stmt_orig = conn.createStatement()
                    rs_orig = stmt_orig.executeQuery(f"SELECT DATA_NASC FROM AROSASSE1.PESSOAS WHERE ID_PESSOA = {id_pessoa}")
                    if rs_orig.next():
                        valor = rs_orig.getString(1)
                        rs_orig.close()
                        stmt_orig.close()
                        if valor:
                            return valor
                    return None
                except Exception as e:
                    print(f"Erro ao buscar data original: {e}")
                    return None

            if data_nasc:
                try:
                    dt = date.fromisoformat(data_nasc)
                    data_valida = java_sql_date.valueOf(dt.isoformat())
                except Exception as e:
                    print(f"Erro ao converter data_nasc: {data_nasc} - {e}")
                    data_original = obter_data_original()
                    if data_original:
                        try:
                            dt_orig = date.fromisoformat(data_original)
                            data_valida = java_sql_date.valueOf(dt_orig.isoformat())
                        except:
                            hoje = date.today()
                            data_valida = java_sql_date.valueOf(hoje.isoformat())
                    else:
                        hoje = date.today()
                        data_valida = java_sql_date.valueOf(hoje.isoformat())
            else:
                data_original = obter_data_original()
                if data_original:
                    try:
                        dt_orig = date.fromisoformat(data_original)
                        data_valida = java_sql_date.valueOf(dt_orig.isoformat())
                    except:
                        hoje = date.today()
                        data_valida = java_sql_date.valueOf(hoje.isoformat())
                else:
                    hoje = date.today()
                    data_valida = java_sql_date.valueOf(hoje.isoformat())

            # ----- UPDATE -----
            sql = """UPDATE AROSASSE1.PESSOAS 
                     SET CPF=?, NOMECOMPL=?, EMAIL=?, TELEFONE=?, DATA_NASC=?, STATUS=?, 
                         CEP=?, ESTADO=?, CIDADE=?, BAIRRO=?, ENDERECO=?, NUMERO=?, COMPL00001=?
                     WHERE ID_PESSOA=?"""
            pstmt = conn.prepareStatement(sql)
            pstmt.setString(1, cpf)
            pstmt.setString(2, nomecompl)
            pstmt.setString(3, email if email else '')
            pstmt.setString(4, telefone)
            pstmt.setDate(5, data_valida)
            pstmt.setString(6, status)
            pstmt.setString(7, cep)
            pstmt.setString(8, estado)
            pstmt.setString(9, cidade)
            pstmt.setString(10, bairro)
            pstmt.setString(11, endereco)
            pstmt.setString(12, numero)
            pstmt.setString(13, complemento)
            pstmt.setInt(14, id_pessoa)

            try:
                rows = pstmt.executeUpdate()
            except Exception as e:
                if 'SQL0803' in str(e):
                    return render(request, 'pessoas/form_pessoa.html', {'erro': 'Este CPF já está cadastrado por outra pessoa.', 'pessoa': request.POST, 'edicao': True})
                raise

            pstmt.close()
            if rows == 0:
                return render(request, 'pessoas/erro.html', {'erro': 'Pessoa não encontrada.'})
            cache.clear()
            next_url = request.POST.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('detalhe_pessoa', id_pessoa=id_pessoa)

        # ----- GET: carregar dados para edição -----
        pstmt = conn.prepareStatement("SELECT * FROM AROSASSE1.PESSOAS WHERE ID_PESSOA = ?")
        pstmt.setFetchSize(2000)
        pstmt.setInt(1, id_pessoa)
        rs = pstmt.executeQuery()
        if rs.next():
            meta = rs.getMetaData()
            num_colunas = meta.getColumnCount()
            pessoa = {}
            for i in range(1, num_colunas + 1):
                nome_col = str(meta.getColumnLabel(i))
                valor = rs.getString(i)
                if valor is not None:
                    valor_str = str(valor)
                    nome_lower = nome_col.lower()
                    if nome_lower == 'data_nasc':
                        if len(valor_str) == 8 and valor_str[2] == '-' and valor_str[5] == '-':
                            ano = int(valor_str[:2])
                            if ano > 50:
                                valor_str = f"19{valor_str}"
                            else:
                                valor_str = f"20{valor_str}"
                        pessoa[nome_lower] = valor_str
                    else:
                        pessoa[nome_lower] = valor_str
                else:
                    pessoa[nome_lower] = None
            rs.close()
            pstmt.close()
            next_url = request.GET.get('next', '')
            return render(request, 'pessoas/form_pessoa.html', {
                'pessoa': pessoa,
                'edicao': True,
                'next_url': next_url,
            })
        else:
            rs.close()
            pstmt.close()
            return render(request, 'pessoas/erro.html', {'erro': 'Pessoa não encontrada.'})
    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})
    
# ==================== EXCLUIR ====================
def excluir_pessoa(request, id_pessoa):
    try:
        conn = pool.get_connection()
        if request.method == 'POST':
            pstmt = conn.prepareStatement("DELETE FROM AROSASSE1.PESSOAS WHERE ID_PESSOA = ?")
            pstmt.setInt(1, id_pessoa)
            rows = pstmt.executeUpdate()
            pstmt.close()
            if rows == 0:
                return render(request, 'pessoas/erro.html', {'erro': 'Pessoa não encontrada.'})
            cache.clear()
            next_url = request.POST.get('next', '')
            if next_url:
               return redirect(next_url)
            return redirect('home')

        # GET: confirmar exclusão
        pstmt = conn.prepareStatement("SELECT NOMECOMPL FROM AROSASSE1.PESSOAS WHERE ID_PESSOA = ?")
        pstmt.setFetchSize(2000)
        pstmt.setInt(1, id_pessoa)
        rs = pstmt.executeQuery()
        if rs.next():
            nome = rs.getString('NOMECOMPL')
            rs.close()
            pstmt.close()
            next_url = request.GET.get('next', '')
            return render(request, 'pessoas/confirmar_exclusao.html', {
                'id_pessoa': id_pessoa,
                'nome': str(nome) if nome else '',
                'next_url': next_url,
            })
        else:
            rs.close()
            pstmt.close()
            return render(request, 'pessoas/erro.html', {'erro': 'Pessoa não encontrada.'})
    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})
    


def buscar_cep_ajax(request):
    """
    View para buscar dados do CEP via AJAX.
    Retorna JSON com os dados do CEP.
    """
    from .ceps import buscar_cep
    from django.http import JsonResponse

    cep = request.GET.get('cep', '').strip()
    if not cep or len(cep) != 8:
        return JsonResponse({'success': False, 'error': 'CEP inválido'})

    dados = buscar_cep(cep)
    if dados:
        return JsonResponse({
            'success': True,
            'uf': dados['sigla_uf'],
            'cidade': dados['nome_municipio'],
            'bairro': dados['localidade'],
            'logradouro': dados['logradouro'],
        })
    else:
        return JsonResponse({'success': False, 'error': 'CEP não encontrado'})

def lista_ceps(request):
    """
    Página para filtrar CEPs por estado, cidade e logradouro.
    Exibe lista paginada com botão para selecionar e ver estabelecimento.
    """
    from .ceps import pool

    # Parâmetros de filtro
    estado = request.GET.get('estado', '').strip().upper()
    cidade = request.GET.get('cidade', '').strip().upper()
    logradouro = request.GET.get('logradouro', '').strip().upper()
    page = int(request.GET.get('page', 1))
    size = int(request.GET.get('size', 20))
    if size > 100:
        size = 100

    conn = pool.get_connection()
    try:
        # Montar cláusula WHERE dinâmica
        where_parts = []
        params = []
        if estado:
            where_parts.append("SIGLA_UF = ?")
            params.append(estado)
        if cidade:
            where_parts.append("UPPER(NOME_MUNICIPIO) LIKE ?")
            params.append(f"%{cidade}%")
        if logradouro:
            where_parts.append("UPPER(LOGRADOURO) LIKE ?")
            params.append(f"%{logradouro}%")
        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        # Contar total
        count_sql = f"SELECT COUNT(*) FROM AROSASSE1.CEPSGEN{where_clause}"
        pstmt_count = conn.prepareStatement(count_sql)
        for i, p in enumerate(params, start=1):
            pstmt_count.setObject(i, p)
        rs_count = pstmt_count.executeQuery()
        rs_count.next()
        total = rs_count.getInt(1)
        rs_count.close()
        pstmt_count.close()

        # Consulta paginada
        offset = (page - 1) * size
        sql = f"""
            SELECT CEP, LOGRADOURO, LOCALIDADE, NOME_MUNICIPIO, SIGLA_UF
            FROM AROSASSE1.CEPSGEN
            {where_clause}
            ORDER BY CEP
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        params_main = params.copy()
        params_main.append(offset)
        params_main.append(size)
        pstmt = conn.prepareStatement(sql)
        pstmt.setFetchSize(2000)
        for i, p in enumerate(params_main, start=1):
            pstmt.setObject(i, p)
        rs = pstmt.executeQuery()

        # Converter resultados para lista de dicionários
        ceps = []
        while rs.next():
            ceps.append({
                'cep': str(rs.getString('CEP')).strip(),
                'logradouro': str(rs.getString('LOGRADOURO')).strip() if rs.getString('LOGRADOURO') else '',
                'localidade': str(rs.getString('LOCALIDADE')).strip() if rs.getString('LOCALIDADE') else '',
                'nome_municipio': str(rs.getString('NOME_MUNICIPIO')).strip() if rs.getString('NOME_MUNICIPIO') else '',
                'sigla_uf': str(rs.getString('SIGLA_UF')).strip() if rs.getString('SIGLA_UF') else '',
            })
        rs.close()
        pstmt.close()

        total_pages = (total + size - 1) // size if size > 0 else 0

        context = {
            'ceps': ceps,
            'page': page,
            'size': size,
            'total': total,
            'total_pages': total_pages,
            'estado': estado,
            'cidade': cidade,
            'logradouro': logradouro,
        }
        return render(request, 'pessoas/lista_ceps.html', context)

    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})


def exibir_estabelecimento(request, cep):
    """
    Exibe o conteúdo do campo ESTABELECIMENTOS (CLOB) para um CEP específico.
    """
    from .ceps import pool

    conn = pool.get_connection()
    try:
        pstmt = conn.prepareStatement("""
            SELECT CEP, ESTABELECIMENTOS
            FROM AROSASSE1.CEPSGEN
            WHERE CEP = ?
        """)
        pstmt.setString(1, cep)
        rs = pstmt.executeQuery()
        if rs.next():
            cep_str = str(rs.getString('CEP')).strip()
            estabelecimento = rs.getString('ESTABELECIMENTOS')  # Pode ser CLOB
            if estabelecimento is not None:
                estabelecimento_str = str(estabelecimento)  # Converte para string Python
            else:
                estabelecimento_str = ''
            rs.close()
            pstmt.close()
            context = {
                'cep': cep_str,
                'estabelecimento': estabelecimento_str,
            }
            return render(request, 'pessoas/estabelecimento.html', context)
        else:
            rs.close()
            pstmt.close()
            return render(request, 'pessoas/erro.html', {'erro': 'CEP não encontrado.'})
    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})  

def exibir_estabelecimento(request, cep):
    """
    Exibe o conteúdo do campo ESTABELECIMENTOS (CLOB) para um CEP específico.
    """
    from .ceps import pool
    from django.http import HttpResponse

    conn = pool.get_connection()
    try:
        pstmt = conn.prepareStatement("""
            SELECT CEP, ESTABELECIMENTOS
            FROM AROSASSE1.CEPSGEN
            WHERE CEP = ?
        """)
        pstmt.setString(1, cep)
        rs = pstmt.executeQuery()
        if rs.next():
            cep_str = str(rs.getString('CEP')).strip()
            estabelecimento = rs.getString('ESTABELECIMENTOS')  # Pode ser CLOB
            if estabelecimento is not None:
                estabelecimento_str = str(estabelecimento)  # Converte para string Python
            else:
                estabelecimento_str = ''
            rs.close()
            pstmt.close()
            context = {
                'cep': cep_str,
                'estabelecimento': estabelecimento_str,
            }
            return render(request, 'pessoas/estabelecimento.html', context)
        else:
            rs.close()
            pstmt.close()
            return render(request, 'pessoas/erro.html', {'erro': 'CEP não encontrado.'})
    except Exception as e:
        return render(request, 'pessoas/erro.html', {'erro': str(e)})
    
def chat_pessoas(request):
    """
    View para o chat com IA (DeepSeek) com suporte a contexto.
    """
    from .chat import processar_pergunta
    from .contexto import limpar_conversa
    from django.http import JsonResponse
    
    # Gerar um ID de sessão (usando a sessão do Django)
    session_id = request.session.session_key
    if not session_id:
        request.session.create()
        session_id = request.session.session_key
    
    if request.method == 'POST':
        pergunta = request.POST.get('pergunta', '').strip()
        acao = request.POST.get('acao', '')
        
        # Limpar conversa
        if acao == 'limpar':
            limpar_conversa(session_id)
            return JsonResponse({
                'success': True,
                'resposta': '🧹 Conversa limpa! Pode começar de novo.'
            })
        
        if not pergunta:
            return JsonResponse({
                'success': False,
                'erro': 'Digite uma pergunta.'
            })
        
        # Processar a pergunta com contexto
        resultado = processar_pergunta(pergunta, session_id)
        
        return JsonResponse(resultado)
    
    # GET - exibe a página do chat
    return render(request, 'pessoas/chat.html')  


def testar_deepseek(request):
    """
    View para testar a conexão com a DeepSeek (nova API).
    """
    from django.http import JsonResponse
    from django.conf import settings
    from openai import OpenAI
    
    try:
        if not settings.DEEPSEEK_API_KEY:
            return JsonResponse({
                'success': False,
                'erro': 'DEEPSEEK_API_KEY não está configurada no .env'
            })
        
        # Criar cliente com a nova API
        client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com/v1",
        )
        
        # Fazer uma chamada de teste
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Você é um assistente."},
                {"role": "user", "content": "Diga 'OK' se estiver funcionando."}
            ],
            max_tokens=10
        )
        
        return JsonResponse({
            'success': True,
            'resposta': response.choices[0].message.content,
            'chave_configurada': True,
            'chave_tamanho': len(settings.DEEPSEEK_API_KEY)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'erro': str(e),
            'chave_configurada': bool(settings.DEEPSEEK_API_KEY)
        })

    
#fim = time.time()
# print(f"Tempo total: {fim - inicio:.2f}s")