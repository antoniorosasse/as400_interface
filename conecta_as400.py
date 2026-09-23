# Conexão com o IBM i (AS400) usando pyodbc
import pyodbc

# 1. Descubra o nome exato do seu driver ODBC
drivers = pyodbc.drivers()
print("Drivers ODBC disponíveis:")
for d in drivers:
    print(f" - {d}")

# 2. Configure a string de conexão
# Substitua os valores entre colchetes pelos seus dados
conn_str = (
    "DRIVER={IBM i Access ODBC Driver};"  # Ou "IBM i Access ODBC Driver 64-bit" [reference:1]
    "SYSTEM=pub400.com;"        # Ex: 192.168.1.100
    "UID=arosasse;"
    "PWD=REDACTED;"
    "DATABASE=arosasse1;"            # Opcional, se necessário
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