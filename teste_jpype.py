import os
import jpype
import jpype.imports
from dotenv import load_dotenv

load_dotenv()

jar_path = "/home/neto/IBM/as400_interface/lib/jt400.jar"

host = os.getenv('AS400_HOST')
user = os.getenv('AS400_USER')
password = os.getenv('AS400_PASSWORD')
library = os.getenv('AS400_LIBRARY')
jdbc_url = f"jdbc:as400://{host};libraries={library};naming=sql"

try:
    if not jpype.isJVMStarted():
        jpype.startJVM(classpath=[jar_path])

    DriverManager = jpype.JClass("java.sql.DriverManager")
    conn = DriverManager.getConnection(jdbc_url, user, password)
    stmt = conn.createStatement()
    rs = stmt.executeQuery("SELECT * FROM PESSOAS FETCH FIRST 5 ROWS ONLY")

    meta = rs.getMetaData()
    num_colunas = meta.getColumnCount()

    # Cabeçalho - converter cada um para Python string
    cabecalho = []
    for i in range(num_colunas):
        # Obtém o label como Java String e converte
        label = meta.getColumnLabel(i + 1)
        cabecalho.append(str(label))  # str() converte Java String para Python str

    print(" | ".join(cabecalho))
    print("-" * 80)

    # Dados
    while rs.next():
        linha = []
        for i in range(1, num_colunas + 1):
            valor = rs.getString(i)
            if valor is None:
                linha.append("NULL")
            else:
                # Converte Java String para Python string usando str()
                # Ou use: linha.append(valor.toString()) -> mas str() é mais seguro
                linha.append(str(valor))
        # IMPORTANTE: usar map(str, linha) garante que tudo seja string Python
        print(" | ".join(map(str, linha)))

    rs.close()
    stmt.close()
    conn.close()

except Exception as e:
    print(f"❌ Erro: {e}")