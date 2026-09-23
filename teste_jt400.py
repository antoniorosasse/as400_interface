import jaydebeapi
import os

# Caminho para o seu arquivo jt400.jar
# Ajuste o caminho para onde você colocou o arquivo
jar_path = "/home/neto/IBM/as400_interface/lib/jt400.jar"

# Credenciais e informações de conexão
host = "pub400.com"
user = "AROSASSE"
password = "REDACTED"
library = "AROSASSE1"

# URL de conexão JDBC para o AS/400
# O parâmetro 'libraries' define a biblioteca padrão, igual ao seu código Java
jdbc_url = f"jdbc:as400://{host};libraries={library};naming=sql"

# Driver JDBC que será usado
driver_class = "com.ibm.as400.access.AS400JDBCDriver"

try:
    # Estabelece a conexão
    # O primeiro argumento é a classe do driver, o segundo é a URL,
    # o terceiro é uma lista com [usuário, senha]
    conn = jaydebeapi.connect(
        driver_class,
        jdbc_url,
        [user, password],
        jar_path,
    )
    print("✅ Conexão estabelecida com sucesso!")

    # Criar um cursor para executar comandos SQL
    curs = conn.cursor()

    # Executar uma consulta simples na sua tabela PESSOAS
    curs.execute("SELECT * FROM PESSOAS FETCH FIRST 5 ROWS ONLY")

    # Buscar e exibir os resultados
    resultados = curs.fetchall()
    for linha in resultados:
        print(linha)

    # Fechar a conexão
    curs.close()
    conn.close()
    print("🔒 Conexão fechada.")

except Exception as e:
    print(f"❌ Erro: {e}")