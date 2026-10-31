# pessoas/tests.py
# Testes do app pessoas. Nenhum toca no AS400: o pool (que abre conexao real)
# e mockado e as classes JDBC (Connection/PreparedStatement/ResultSet) sao
# substituidas por dubles em memoria.
import csv
from io import StringIO
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from . import views


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
