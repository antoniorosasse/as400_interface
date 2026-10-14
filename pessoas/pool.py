# pool.py
# Gerencia uma conexao JDBC unica com o AS400, com validacao antes de entregar.
import logging
import time

from .as400_conn import get_connection

logger = logging.getLogger(__name__)


class ConnectionPool:
    def __init__(self, max_age=300, valid_timeout=2):
        self.conn = None
        self.last_used = 0
        self.max_age = max_age
        self.valid_timeout = valid_timeout

    def _fechar_atual(self):
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        self.conn = None

    def _criar_nova(self):
        self._fechar_atual()
        self.conn = get_connection()
        self.last_used = time.time()

    def get_connection(self):
        now = time.time()

        # 1) Sem conexao ou passou do max_age -> cria nova
        if self.conn is None or (now - self.last_used) > self.max_age:
            self._criar_nova()
            return self.conn

        # 2) Conexao "velha" mas dentro do max_age -> valida antes de entregar
        try:
            if not self.conn.isValid(self.valid_timeout):
                logger.info("Conexao AS/400 invalida, recriando.")
                self._criar_nova()
        except Exception as exc:
            logger.warning("Erro ao validar conexao AS/400 (%s), recriando.", exc)
            self._criar_nova()

        self.last_used = now
        return self.conn

    def fechar(self):
        """Fecha a conexao atual (usado em shutdown / testes)."""
        self._fechar_atual()


pool = ConnectionPool(max_age=300)
