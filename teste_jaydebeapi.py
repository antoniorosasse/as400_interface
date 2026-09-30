import os
import jaydebeapi
from dotenv import load_dotenv

load_dotenv()

jar_path = "/home/neto/IBM/as400_interface/lib/jt400.jar"
host = os.getenv('AS400_HOST')
user = os.getenv('AS400_USER')
password = os.getenv('AS400_PASSWORD')
library = os.getenv('AS400_LIBRARY')
jdbc_url = f"jdbc:as400://{host};libraries={library};naming=sql"

conn = jaydebeapi.connect(
    "com.ibm.as400.access.AS400JDBCDriver",
    jdbc_url,
    [user, password],
    jar_path,
)
curs = conn.cursor()
curs.execute("SELECT * FROM PESSOAS FETCH FIRST 5 ROWS ONLY")
for row in curs.fetchall():
    print(row)  # row é uma tupla com strings Python nativas
curs.close()
conn.close()