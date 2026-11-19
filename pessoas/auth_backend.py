# /home/neto/IBM/as400_interface/pessoas/auth_backend.py
"""
Autenticacao com o banco de usuarios do cnpj_interface (fonte unica).

Sem acentos no codigo. Comentarios em PT-BR sem acento.

Como funciona
-------------
O as400_interface nao tem usuarios proprios: quem manda na senha e' o
Postgres do cnpj_interface (alias de banco "usuarios", configurado pelas
variaveis USUARIOS_DB_* do .env). A cada login:

  1. busca o usuario em auth_user do cnpj (somente leitura);
  2. confere a senha com o hash de la' (check_password: e' so' matematica de
     hash, nao precisa de senha do banco nem de permissao de escrita);
  3. se bater, espelha o usuario no sqlite local (hash, e-mail, nome e flags),
     para o admin, as permissoes e as sessoes continuarem funcionando.

Regras de decisao
-----------------
- cnpj respondeu: ele e' a verdade. Usuario inexistente ou senha errada =
  login negado, mesmo que o espelho local tenha uma senha antiga valida.
- cnpj nao respondeu (indisponivel/timeout): modo degradado, valida pelo
  espelho local e registra um warning no log.
- Alias "usuarios" ausente (dev sem Postgres, servidor sem a variavel): idem
  modo degradado.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db import DatabaseError

logger = logging.getLogger(__name__)

ALIAS_USUARIOS = 'usuarios'

# Campos copiados do cnpj para o espelho local. "password" vai junto de
# proposito: e' o hash, nao a senha - e' o que permite o modo degradado.
CAMPOS_ESPELHADOS = (
    'password',
    'email',
    'first_name',
    'last_name',
    'is_active',
    'is_staff',
    'is_superuser',
)


def alias_disponivel():
    """True quando o alias do Postgres do cnpj esta configurado no .env."""
    return ALIAS_USUARIOS in settings.DATABASES


def buscar_usuario_remoto(username):
    """Busca o usuario em auth_user do cnpj_interface (uma query, sem escrita)."""
    User = get_user_model()
    gerenciador = User.objects.db_manager(ALIAS_USUARIOS)
    return gerenciador.filter(**{User.USERNAME_FIELD: username}).first()


def espelhar_usuario(remoto):
    """Cria/atualiza o usuario local com os dados do cnpj e devolve o local."""
    User = get_user_model()
    local, _criado = User.objects.get_or_create(
        **{User.USERNAME_FIELD: getattr(remoto, User.USERNAME_FIELD)}
    )
    for campo in CAMPOS_ESPELHADOS:
        setattr(local, campo, getattr(remoto, campo))
    local.save()
    return local


class BackendCnpjPostgres(ModelBackend):
    """ModelBackend que valida a senha no cnpj_interface e espelha o usuario."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        username = User.normalize_username(username)

        if not alias_disponivel():
            logger.debug(
                'Alias "%s" ausente: login pelo espelho local (%s).',
                ALIAS_USUARIOS, username,
            )
            return super().authenticate(
                request, username=username, password=password, **kwargs
            )

        try:
            remoto = buscar_usuario_remoto(username)
        except DatabaseError as erro:
            logger.warning(
                'Banco de usuarios indisponivel (%s): login pelo espelho local (%s).',
                type(erro).__name__, username,
            )
            return super().authenticate(
                request, username=username, password=password, **kwargs
            )

        if remoto is None:
            logger.info('Login negado: "%s" nao existe no banco de usuarios.', username)
            return None
        if not self.user_can_authenticate(remoto) or not remoto.check_password(password):
            logger.info('Login negado: senha invalida para "%s".', username)
            return None

        local = espelhar_usuario(remoto)
        return local if self.user_can_authenticate(local) else None
