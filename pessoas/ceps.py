# pessoas/ceps.py
from .pool import pool
import logging

logger = logging.getLogger(__name__)

def buscar_cep(cep):
    """
    Busca um CEP na tabela CEPSGEN e retorna um dicionário com os dados.
    Retorna None se não encontrado.
    """
    # Remove caracteres não numéricos e garante 8 dígitos
    cep_clean = ''.join(filter(str.isdigit, str(cep))).strip()
    if len(cep_clean) != 8:
        return None

    conn = pool.get_connection()
    try:
        # Usar prepared statement para evitar injeção
        pstmt = conn.prepareStatement("""
            SELECT CEP, LOGRADOURO, LOCALIDADE, NOME_MUNICIPIO, SIGLA_UF
            FROM AROSASSE1.CEPSGEN
            WHERE CEP = ?
        """)
        pstmt.setString(1, cep_clean)
        rs = pstmt.executeQuery()

        if rs.next():
            dados = {
                'cep': cep_clean,
                'logradouro': str(rs.getString('LOGRADOURO')).strip() if rs.getString('LOGRADOURO') else '',
                'localidade': str(rs.getString('LOCALIDADE')).strip() if rs.getString('LOCALIDADE') else '',
                'nome_municipio': str(rs.getString('NOME_MUNICIPIO')).strip() if rs.getString('NOME_MUNICIPIO') else '',
                'sigla_uf': str(rs.getString('SIGLA_UF')).strip() if rs.getString('SIGLA_UF') else '',
            }
            rs.close()
            pstmt.close()
            return dados
        else:
            rs.close()
            pstmt.close()
            return None
    except Exception as e:
        logger.error(f"Erro ao buscar CEP {cep_clean}: {e}")
        return None