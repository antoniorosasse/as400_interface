# Django URL Configuration
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path
from django.views.generic import RedirectView
from pessoas import views
from django.http import HttpResponse
from pessoas.views import (
    listar_pessoas,
    pessoas_paginadas,
    exportar_csv,
    api_pessoas,
    detalhe_pessoa,
    criar_pessoa,
    editar_pessoa,
    excluir_pessoa,
    buscar_cep_ajax,
    lista_ceps,                   
    exibir_estabelecimento,  
    testar_deepseek,           
)
from pessoas.views import chat_pessoas


urlpatterns = [
    path('admin/', admin.site.urls),

    # Logout proprio: o do admin encerra a sessao mas volta para a tela do
    # admin. Este encerra a mesma sessao e devolve para o login (POST, CSRF).
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Página inicial agora é a paginada
    path('', login_required(views.pessoas_paginadas), name='home'),

    # Redireciona /pessoas/ para /pessoas/paginadas/
    path('pessoas/', RedirectView.as_view(pattern_name='pessoas_paginadas', permanent=False)),

    # Rotas originais (dados de pessoas exigem login; CEP e health ficam publicos)
    path('pessoas/paginadas/', login_required(views.pessoas_paginadas), name='pessoas_paginadas'),
    path('pessoas/exportar/', login_required(views.exportar_csv), name='exportar_csv'),
    path('api/pessoas/', login_required(views.api_pessoas), name='api_pessoas'),
    path('pessoas/<int:id_pessoa>/', login_required(views.detalhe_pessoa), name='detalhe_pessoa'),
    path('pessoas/novo/', login_required(views.criar_pessoa), name='criar_pessoa'),
    path('pessoas/<int:id_pessoa>/editar/', login_required(views.editar_pessoa), name='editar_pessoa'),
    path('pessoas/<int:id_pessoa>/excluir/', login_required(views.excluir_pessoa), name='excluir_pessoa'),
    path('buscar-cep/', buscar_cep_ajax, name='buscar_cep'),
    path('lista-ceps/', lista_ceps, name='lista_ceps'),
    path('estabelecimento/<str:cep>/', exibir_estabelecimento, name='exibir_estabelecimento'),
    path('chat-pessoas/', login_required(chat_pessoas), name='chat_pessoas'),
    path('testar-deepseek/', login_required(testar_deepseek), name='testar_deepseek'),
    path('health/', lambda r: HttpResponse('ok'), name='health'),
    path('health/deep/', views.health_deep, name='health_deep'),
]