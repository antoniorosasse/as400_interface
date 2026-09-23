import ibm_db
import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv('AS400_HOST')
user = os.getenv('AS400_USER')
password = os.getenv('AS400_PASSWORD')
library = os.getenv('AS400_LIBRARY')

# Opção 1: Conectar com DATABASE=*LOCAL e definir o schema com DBQ (ou CurrentSchema)
conn_str = (
    f"HOSTNAME={host};"
    f"PORT=446;"
    f"PROTOCOL=TCPIP;"
    f"UID={user};"
    f"PWD={password};"    
)

print("Tentando conectar com:", conn_str)
conn = ibm_db.connect(conn_str, "", "")

if conn:
    print("✅ Conexão estabelecida com sucesso!")
    # Testar consulta simples
    stmt = ibm_db.exec_immediate(conn, "SELECT * FROM AROSASSE1.PESSOAS FETCH FIRST 1 ROW ONLY")
    if ibm_db.fetch_row(stmt):
        print("Dados encontrados!")
    ibm_db.close(conn)
else:
    print("❌ Falha na conexão.")