# pool.py
# Este arquivo define uma classe ConnectionPool que gerencia uma conexão com o AS400 usando JDBC
import time
from .as400_conn import get_connection

class ConnectionPool:
    def __init__(self, max_age=30):
        self.conn = None
        self.last_used = 0
        self.max_age = max_age

    def get_connection(self):
        now = time.time()
        if self.conn is None or (now - self.last_used) > self.max_age:
            if self.conn:
                try:
                    self.conn.close()
                except:
                    pass
            self.conn = get_connection()
            self.last_used = now
        else:
            self.last_used = now
        return self.conn

pool = ConnectionPool(max_age=30)