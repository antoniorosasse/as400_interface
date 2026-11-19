# /home/neto/IBM/as400_interface/pessoas/context_processors.py
"""
Variaveis de site comuns a todos os templates (pessoas/base.html).

Sem acentos no codigo. Comentarios em PT-BR sem acento.
"""

from django.conf import settings


# Porta do menu_interface no runserver local: e' ele quem serve o portfolio
# (arosasse.tec.br) em /menu/.
PORTA_MENU_DEV = 8000

# Producao: o portfolio tem dominio proprio, servido pelo menu.service.
PORTFOLIO_PRODUCAO = 'https://arosasse.tec.br/'


def url_portfolio(request=None):
    """
    URL do portfolio de projetos (menu_interface).

    Ordem de resolucao:
      1. PORTFOLIO_URL do .env, quando definida (vence sempre);
      2. DEBUG=True  -> http://<host>:8000/menu/  (preview no dev);
      3. producao    -> https://arosasse.tec.br/

    O caminho /menu/ responde em qualquer Host, entao o link do dev nao
    depende do HOSTS_COMERCIAL configurado no menu_interface.

    Usada pela marca e pelo item Inicio de pessoas/base.html.
    """
    url = getattr(settings, 'PORTFOLIO_URL', '').strip()
    if url:
        return url
    if settings.DEBUG:
        host = request.get_host().split(':')[0] if request else 'localhost'
        return f'http://{host}:{PORTA_MENU_DEV}/menu/'
    return PORTFOLIO_PRODUCAO


def links_do_site(request):
    """Expoe portfolio_url para os templates (marca e item Inicio do menu)."""
    return {'portfolio_url': url_portfolio(request)}
