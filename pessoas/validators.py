import re

def limpar_telefone(telefone):
    """Remove caracteres não numéricos e limita a 15 dígitos."""
    if not telefone:
        return ''
    telefone = re.sub(r'\D', '', telefone)  # remove tudo que não é dígito
    return telefone[:15]  # máximo 15 caracteres

def limpar_cep(cep):
    """Remove caracteres não numéricos e limita a 8 dígitos."""
    if not cep:
        return ''
    cep = re.sub(r'\D', '', cep)
    return cep[:8]

def limpar_estado(estado):
    """Converte para maiúsculas e remove espaços."""
    if not estado:
        return ''
    return estado.strip().upper()[:2]

def validar_cpf(cpf):
    """Valida se CPF tem 11 dígitos (apenas números)."""
    if not cpf:
        return False
    cpf = re.sub(r'\D', '', cpf)
    return len(cpf) == 11

def validar_email(email):
    """Valida formato básico de email."""
    if not email:
        return True  # opcional, pode ser vazio
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
# pessoas/validators.py (adicione no final)
from .ceps import buscar_cep
from django.core.exceptions import ValidationError

def validar_cep_existe(cep):
    """
    Valida se o CEP existe na tabela CEPSGEN.
    Retorna os dados do CEP se existir, ou levanta ValidationError.
    """
    dados = buscar_cep(cep)
    if dados is None:
        raise ValidationError("CEP não encontrado na base de dados. Verifique o número informado.")
    return dados