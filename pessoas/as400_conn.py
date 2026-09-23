# Arquivo: pessoas/as400_conn.py
# Este arquivo contém funções para iniciar a JVM e estabelecer uma conexão com o AS400 usando JDBC
import os
import jpype
import jpype.imports
from django.conf import settings

# Caminho absoluto para o jt400.jar dentro do projeto
JAR_PATH = os.path.join(settings.BASE_DIR, 'lib', 'jt400.jar')

def iniciar_jvm():
    if not jpype.isJVMStarted():
        # Verifica se o arquivo existe
        if not os.path.exists(JAR_PATH):
            raise FileNotFoundError(f"Arquivo jt400.jar não encontrado em: {JAR_PATH}")
        jpype.startJVM(classpath=[JAR_PATH])
        print("JVM iniciada com sucesso.")

def get_connection():
    iniciar_jvm()
    host = settings.AS400_HOST
    user = settings.AS400_USER
    password = settings.AS400_PASSWORD
    library = settings.AS400_LIBRARY
    jdbc_url = f"jdbc:as400://{host};libraries={library};naming=sql"
    DriverManager = jpype.JClass("java.sql.DriverManager")
    return DriverManager.getConnection(jdbc_url, user, password)