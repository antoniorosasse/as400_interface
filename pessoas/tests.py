# pessoas/tests.py
# Testes do app pessoas. Nenhum toca no AS400: o pool (que abre conexao real)
# e mockado e as classes JDBC (Connection/PreparedStatement/ResultSet) sao
# substituidas por dubles em memoria.
import csv
from io import StringIO
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import PBKDF2PasswordHasher, check_password, make_password
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from . import auth_backend, views
from .context_processors import url_portfolio


class _FakeMetaData:
    """Duble de java.sql.ResultSetMetaData."""

    LABELS = ['ID_PESSOA', 'NOMECOMPL']

    def getColumnCount(self):
        return len(self.LABELS)

    def getColumnLabel(self, indice):
        return self.LABELS[indice - 1]


class _FakeResultSet:
    """Duble de java.sql.ResultSet, percorrido com next()/getString()."""

    def __init__(self, linhas):
        self._linhas = list(linhas)
        self._pos = -1
        self.fechado = False

    def getMetaData(self):
        return _FakeMetaData()

    def next(self):
        self._pos += 1
        return self._pos < len(self._linhas)

    def getString(self, indice):
        return self._linhas[self._pos][indice - 1]

    def getInt(self, indice):
        return len(self._linhas)

    def close(self):
        self.fechado = True


class _FakePreparedStatement:
    """Duble de java.sql.PreparedStatement."""

    def __init__(self, resultset):
        self._resultset = resultset
        self.fetch_size = None
        self.parametros = []
        self.fechado = False

    def setString(self, indice, valor):
        self.parametros.append(valor)

    def setFetchSize(self, tamanho):
        self.fetch_size = tamanho

    def executeQuery(self):
        return self._resultset

    def close(self):
        self.fechado = True


class _FakeConnection:
    """Duble de java.sql.Connection: serve o COUNT(*) e a query principal."""

    def __init__(self, linhas):
        self.linhas = list(linhas)
        self.statements = []
        self.rs_count = _FakeResultSet([(str(len(self.linhas)),)])
        self.rs_principal = _FakeResultSet(self.linhas)

    def prepareStatement(self, sql):
        if 'COUNT(' in sql:
            pstmt = _FakePreparedStatement(self.rs_count)
        else:
            pstmt = _FakePreparedStatement(self.rs_principal)
        self.statements.append((sql, pstmt))
        return pstmt


class ExportarCsvTests(SimpleTestCase):
    def _exportar(self, linhas, **query):
        fake = _FakeConnection(linhas)
        request = RequestFactory().get('/pessoas/exportar-csv/', query)
        with patch.object(views.pool, 'get_connection', return_value=fake), \
                patch('builtins.print'):
            response = views.exportar_csv(request)
            # O gerador e preguicoso: consumir aqui mantem o print silenciado
            # e garante que o ResultSet foi fechado dentro do teste.
            pedacos = list(response._iterator) if hasattr(response, '_iterator') else None
        return fake, response, pedacos

    def test_streaming_entrega_bytes_utf8(self):
        fake, response, pedacos = self._exportar(
            [(1, 'JOSE ANTONIO'), (2, 'MARIA JOSÉ')])

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/csv'))
        self.assertIn('charset=utf-8', response['Content-Type'])
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('pessoas_todos.csv', response['Content-Disposition'])

        # _iterator entrega o que o gerador da view produz, sem o make_bytes
        # do Django -- assim o teste prova que os pedacos ja saem em bytes.
        self.assertEqual(len(pedacos), 3)
        self.assertTrue(all(isinstance(p, bytes) for p in pedacos), pedacos)
        self.assertEqual(
            b''.join(pedacos),
            'ID_PESSOA,NOMECOMPL\n1,JOSE ANTONIO\n2,MARIA JOSÉ\n'.encode('utf-8'),
        )
        self.assertTrue(fake.rs_principal.fechado)

    def test_campos_com_virgula_e_aspas_sao_escapados(self):
        # Enderecos de PESSOAS trazem virgula ("ALA A, QD 12"): sem quoting a
        # linha ganharia colunas extras e o CSV ficaria corrompido.
        _, response, pedacos = self._exportar(
            [(3, 'ANA "A", SILVA; CENTRO')])

        self.assertEqual(response.status_code, 200)
        corpo = b''.join(pedacos).decode('utf-8')
        self.assertEqual(
            corpo,
            'ID_PESSOA,NOMECOMPL\n3,"ANA ""A"", SILVA; CENTRO"\n',
        )
        linhas = list(csv.reader(StringIO(corpo)))
        self.assertEqual(linhas, [['ID_PESSOA', 'NOMECOMPL'],
                                  ['3', 'ANA "A", SILVA; CENTRO']])

    def test_filtro_por_nome_usa_prepared_statement(self):
        fake, response, pedacos = self._exportar([(7, 'JOSE ANTONIO')], nome='jose')

        sql, pstmt = fake.statements[-1]
        self.assertIn('WHERE UPPER(NOMECOMPL) LIKE ?', sql)
        self.assertEqual(pstmt.parametros, ['%JOSE%'])
        self.assertEqual(pstmt.fetch_size, 2000)
        self.assertIn('pessoas_jose.csv', response['Content-Disposition'])
        self.assertEqual(
            b''.join(pedacos),
            'ID_PESSOA,NOMECOMPL\n7,JOSE ANTONIO\n'.encode('utf-8'),
        )

    def test_cabecalho_sozinho_quando_nao_ha_registros(self):
        fake, response, pedacos = self._exportar([])

        self.assertEqual(b''.join(pedacos), b'ID_PESSOA,NOMECOMPL\n')
        self.assertTrue(fake.rs_principal.fechado)

    def test_erro_no_jdbc_renderiza_pagina_de_erro(self):
        request = RequestFactory().get('/pessoas/exportar-csv/')
        with patch.object(views.pool, 'get_connection',
                          side_effect=RuntimeError('pub400 fora do ar')), \
                patch('builtins.print'):
            response = views.exportar_csv(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'pub400 fora do ar', response.content)

    def test_download_abortado_fecha_resultset_e_statement(self):
        # Cliente cancela o download no meio: o gerador recebe GeneratorExit.
        # Sem try/finally o cursor fica preso na conexao unica do pool e o
        # proximo request falha com "Cursor state not valid".
        fake = _FakeConnection([(1, 'JOSE ANTONIO'), (2, 'MARIA')])
        request = RequestFactory().get('/pessoas/exportar-csv/')
        with patch.object(views.pool, 'get_connection', return_value=fake), \
                patch('builtins.print'):
            response = views.exportar_csv(request)
            iterator = response._iterator
            next(iterator)  # cabecalho
            next(iterator)  # primeira linha
            iterator.close()  # simula o download abortado

        pstmt_count, pstmt_principal = [pstmt for _, pstmt in fake.statements]
        self.assertTrue(fake.rs_principal.fechado)
        self.assertTrue(pstmt_principal.fechado)
        self.assertTrue(pstmt_count.fechado)

    def test_download_cancelado_antes_do_primeiro_pedaco_fecha_recursos(self):
        # Cliente desconecta antes do primeiro pedaco: o Django fecha a
        # resposta sem nunca iterar. Gerador comum nao executaria o finally
        # nesse caso (gerador nao iniciado) -- por isso o _CsvStream da view.
        fake = _FakeConnection([(1, 'JOSE ANTONIO')])
        request = RequestFactory().get('/pessoas/exportar-csv/')
        with patch.object(views.pool, 'get_connection', return_value=fake), \
                patch('builtins.print'):
            response = views.exportar_csv(request)
            response.close()  # o handler do Django faz o mesmo no abort

        pstmt_count, pstmt_principal = [pstmt for _, pstmt in fake.statements]
        self.assertTrue(fake.rs_principal.fechado)
        self.assertTrue(pstmt_principal.fechado)
        self.assertTrue(pstmt_count.fechado)

    def test_erro_na_query_principal_fecha_statement(self):
        # Falha antes de existir ResultSet (ex: SQL0901): o Statement tambem
        # precisa ser fechado, senao a conexao do pool fica com cursor aberto.
        fake = _FakeConnection([])
        prepare_statement_original = fake.prepareStatement
        principal = _FakePreparedStatement(fake.rs_principal)

        def execute_query_com_erro():
            raise RuntimeError('SQL0901 falha no servidor')

        principal.executeQuery = execute_query_com_erro

        def prepare_statement(sql):
            if 'COUNT(' not in sql:
                fake.statements.append((sql, principal))
                return principal
            return prepare_statement_original(sql)

        fake.prepareStatement = prepare_statement
        request = RequestFactory().get('/pessoas/exportar-csv/')
        with patch.object(views.pool, 'get_connection', return_value=fake), \
                patch('builtins.print'):
            response = views.exportar_csv(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'SQL0901', response.content)
        self.assertTrue(principal.fechado)


class LoginObrigatorioTests(TestCase):
    """Telas de pessoas exigem login; health continua publico.

    Nenhum teste aqui abre conexao com o AS/400: ou o decorator intercepta
    (302), ou a rota usada nao consulta o banco.
    """

    ROTAS_PROTEGIDAS = [
        ('home', None),
        ('pessoas_paginadas', None),
        ('exportar_csv', None),
        ('api_pessoas', None),
        ('criar_pessoa', None),
        ('detalhe_pessoa', (1,)),
        ('editar_pessoa', (1,)),
        ('excluir_pessoa', (1,)),
        ('chat_pessoas', None),
        ('testar_deepseek', None),
    ]

    def test_rotas_de_pessoas_redirecionam_para_login(self):
        for nome, args in self.ROTAS_PROTEGIDAS:
            with self.subTest(rota=nome):
                resposta = self.client.get(reverse(nome, args=args))
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(
                    resposta['Location'].startswith(settings.LOGIN_URL),
                    resposta['Location'],
                )

    def test_formulario_novo_acessivel_apos_login(self):
        # /pessoas/novo/ (GET) so renderiza o formulario, sem tocar no AS/400.
        usuario = User.objects.create_user('teste_login', password='senha-teste-123')
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse('criar_pessoa')).status_code, 200)

    def test_login_de_usuario_comum_entra_no_sistema(self):
        # A tela de login e a do sistema (nao a do admin), entao usuario
        # ativo sem is_staff tambem entra -- caso do usuario 'demo'.
        User.objects.create_user('teste_comum', password='senha-teste-123')
        resposta = self.client.post(reverse('login'), {
            'username': 'teste_comum',
            'password': 'senha-teste-123',
        })
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.client.get(reverse('criar_pessoa')).status_code, 200)

    def test_health_continua_publico(self):
        # Monitoracao (acompanha_flip_dns.sh) nao pode receber 302.
        self.assertEqual(self.client.get(reverse('health')).status_code, 200)

    def test_logout_encerra_a_sessao(self):
        usuario = User.objects.create_user('teste_saida', password='senha-teste-123')
        self.client.force_login(usuario)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)
        self.assertEqual(self.client.get(reverse('home')).status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)


def _hash(senha, iteracoes=None):
    """Hash pbkdf2_sha256. Com `iteracoes`, simula um hash antigo do cnpj."""
    if iteracoes is None:
        return make_password(senha)
    hasher = PBKDF2PasswordHasher()
    hasher.iterations = iteracoes
    return hasher.encode(senha, hasher.salt())


class _UsuarioRemoto:
    """Duble do User vindo do Postgres do cnpj_interface."""

    def __init__(self, username='remoto', senha='senha-certa',
                 is_active=True, is_staff=False, is_superuser=False,
                 iteracoes=None):
        self.username = username
        self.password = _hash(senha, iteracoes)
        self.email = f'{username}@exemplo.test'
        self.first_name = 'Nome'
        self.last_name = 'Remoto'
        self.is_active = is_active
        self.is_staff = is_staff
        self.is_superuser = is_superuser

    def check_password(self, senha):
        # Reproduz o User.check_password do Django: quando o hash esta'
        # desatualizado ele chama o setter, que regrava a senha (UPDATE).
        def setter(nova_senha):
            self.save(update_fields=['password'])

        return check_password(senha, self.password, setter)

    def save(self, **kwargs):
        # O role do cnpj so' tem SELECT: qualquer escrita aqui e' o bug que
        # derrubava o login com 500 (permission denied for table auth_user).
        raise AssertionError(
            'tentativa de gravar no auth_user do cnpj (role somente leitura)'
        )


class BackendCnpjPostgresTests(TestCase):
    """Login valida no cnpj_interface e espelha o usuario no sqlite local."""

    def setUp(self):
        # Nos testes o alias "usuarios" nao e' criado (settings.RODANDO_TESTES),
        # entao sem este patch o backend cairia direto no espelho local.
        patcher = patch('pessoas.auth_backend.alias_disponivel', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _autenticar(self, username, senha):
        return auth_backend.BackendCnpjPostgres().authenticate(
            None, username=username, password=senha
        )

    def test_senha_do_cnpj_autentica_e_espelha_o_usuario(self):
        remoto = _UsuarioRemoto('neto', 'senha-certa', is_staff=True, is_superuser=True)
        with patch('pessoas.auth_backend.buscar_usuario_remoto', return_value=remoto):
            local = self._autenticar('neto', 'senha-certa')

        self.assertIsNotNone(local)
        self.assertEqual(local.username, 'neto')
        self.assertTrue(local.is_staff)
        self.assertTrue(local.is_superuser)
        self.assertEqual(local.email, 'neto@exemplo.test')
        # o hash veio junto: o espelho aceita a mesma senha (modo degradado)
        self.assertTrue(User.objects.get(username='neto').check_password('senha-certa'))

    def test_senha_errada_no_cnpj_nao_entra_mesmo_com_espelho_valido(self):
        # Senha trocada no cnpj: o espelho local nao pode continuar aceitando
        # a senha antiga.
        User.objects.create_user('neto', password='senha-antiga')
        remoto = _UsuarioRemoto('neto', 'senha-nova')
        with patch('pessoas.auth_backend.buscar_usuario_remoto', return_value=remoto):
            self.assertIsNone(self._autenticar('neto', 'senha-antiga'))

    def test_hash_antigo_autentica_sem_escrever_no_cnpj(self):
        # Hash com iteracoes antigas: o User.check_password do Django chamaria
        # o setter e tentaria UPDATE em auth_user (role so' leitura = 500).
        # Aqui o login tem que passar sem nenhuma escrita no banco do cnpj.
        remoto = _UsuarioRemoto('demo', 'senha-certa', iteracoes=1000)
        with patch('pessoas.auth_backend.buscar_usuario_remoto', return_value=remoto):
            local = self._autenticar('demo', 'senha-certa')

        self.assertIsNotNone(local)
        self.assertEqual(local.username, 'demo')
        # o espelho local guardou o hash como veio do cnpj
        self.assertEqual(User.objects.get(username='demo').password, remoto.password)

    def test_usuario_inexistente_no_cnpj_e_negado(self):
        User.objects.create_user('fantasma', password='senha-teste-123')
        with patch('pessoas.auth_backend.buscar_usuario_remoto', return_value=None):
            self.assertIsNone(self._autenticar('fantasma', 'senha-teste-123'))

    def test_usuario_inativo_no_cnpj_e_negado(self):
        remoto = _UsuarioRemoto('bloqueado', 'senha-certa', is_active=False)
        with patch('pessoas.auth_backend.buscar_usuario_remoto', return_value=remoto):
            self.assertIsNone(self._autenticar('bloqueado', 'senha-certa'))

    def test_postgres_fora_do_ar_cai_no_espelho_local(self):
        User.objects.create_user('neto', password='senha-teste-123')
        with patch('pessoas.auth_backend.buscar_usuario_remoto',
                   side_effect=DatabaseError('fora do ar')):
            local = self._autenticar('neto', 'senha-teste-123')

        self.assertIsNotNone(local)
        self.assertEqual(local.username, 'neto')

    def test_sem_alias_configurado_usa_o_espelho_local(self):
        User.objects.create_user('local', password='senha-teste-123')
        with patch('pessoas.auth_backend.alias_disponivel', return_value=False):
            local = self._autenticar('local', 'senha-teste-123')

        self.assertIsNotNone(local)
        self.assertEqual(local.username, 'local')


class LinksDoSiteTests(TestCase):
    """Marca e item Inicio levam ao portfolio; a lista de pessoas fica em Pessoas."""

    @override_settings(PORTFOLIO_URL='', DEBUG=False)
    def test_url_portfolio_padrao_de_producao(self):
        self.assertEqual(url_portfolio(), 'https://arosasse.tec.br/')

    @override_settings(PORTFOLIO_URL='https://exemplo.test/pt/', DEBUG=False)
    def test_url_portfolio_vem_do_env(self):
        self.assertEqual(url_portfolio(), 'https://exemplo.test/pt/')

    @override_settings(PORTFOLIO_URL='', DEBUG=True)
    def test_url_portfolio_no_dev_usa_o_menu_na_8000(self):
        requisicao = RequestFactory().get('/', HTTP_HOST='localhost:8001')
        self.assertEqual(url_portfolio(requisicao), 'http://localhost:8000/menu/')

    @override_settings(PORTFOLIO_URL='', DEBUG=False)
    def test_nav_do_base_leva_ao_portfolio_e_tem_item_pessoas(self):
        usuario = User.objects.create_user('teste_nav', password='senha-teste-123')
        self.client.force_login(usuario)
        html = self.client.get(reverse('criar_pessoa')).content.decode()

        # marca + item Inicio
        self.assertEqual(html.count('href="https://arosasse.tec.br/"'), 2)
        self.assertIn('> Início', html)
        # a lista de pessoas continua no menu, agora como "Pessoas"
        self.assertIn(f'href="{reverse("home")}"', html)
        self.assertIn('> Pessoas', html)


