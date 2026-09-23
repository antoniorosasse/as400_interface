# pessoas/apps.py
# Este arquivo define a configuração do aplicativo Django "pessoas". Ele herda de AppConfig e especifica o nome do aplicativo. Além disso, no método ready(), ele importa a função iniciar_jvm do módulo as400_conn e a chama para iniciar a JVM quando o aplicativo é carregado. Isso é útil para garantir que a JVM esteja pronta para uso antes de qualquer operação que dependa dela.  
from django.apps import AppConfig


class PessoasConfig(AppConfig):
    name = 'pessoas'

    def ready(self):
        # Importa a função e inicia a JVM ao carregar o app
        from .as400_conn import iniciar_jvm
        iniciar_jvm()