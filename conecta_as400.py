# Conexão com o IBM i (AS400) usando pyodbc
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

# 1. Descubra o nome exato do seu driver ODBC
drivers = pyodbc.drivers()
print("Drivers ODBC disponíveis:")
for d in drivers:
    print(f" - {d}")

# 2. Configure a string de conexão (le do .env)
conn_str = (
    "DRIVER={IBM i Access ODBC Driver};"
    f"SYSTEM={os.getenv('AS400_HOST')};"
    f"UID={os.getenv('AS400_USER')};"
    f"PWD={os.getenv('AS400_PASSWORD')};"
    f"DATABASE={os.getenv('AS400_LIBRARY')};"
)

try:
    # 3. Estabelecer a conexão
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    print("Conexão com o IBM i (AS400) estabelecida com sucesso!")

    # 4. Executar a consulta na sua tabela
    query = "SELECT * FROM AROSASSE1.PESSOAS"
    cursor.execute(query)

    # 5. Exibir os resultados
    print("\n--- Dados da Tabela PESSOAS ---")
    colunas = [desc[0] for desc in cursor.description]
    print(" | ".join(colunas))
    print("-" * 80)

    for row in cursor.fetchall():
        print(" | ".join(str(valor) for valor in row))

    # 6. Fechar a conexão
    cursor.close()
    conn.close()
    print("\nConexão fechada.")

except Exception as e:
    print(f"Erro ao conectar ou executar a consulta: {e}")