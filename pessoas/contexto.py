# pessoas/contexto.py
import re
import json
import logging
from datetime import datetime
from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# Configurar o cliente OpenAI
client = OpenAI(
    api_key=settings.DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",
)

class ConversaContexto:
    """
    Gerencia o contexto da conversa com o usuário usando IA para extrair informações.
    """
    
    def __init__(self, max_historico=5):
        self.historico = []
        self.max_historico = max_historico
        self.contexto = {}
        self._ultima_pergunta = None
        self._ultima_resposta = None
    
    def adicionar_interacao(self, pergunta, resposta, sql=None):
        """Adiciona uma interação ao histórico e extrai contexto"""
        self.historico.append({
            'pergunta': pergunta,
            'resposta': resposta,
            'sql': sql,
            'timestamp': datetime.now().isoformat()
        })
        
        # Manter apenas as últimas N interações
        if len(self.historico) > self.max_historico:
            self.historico.pop(0)
        
        # Extrair contexto usando IA
        self._extrair_contexto_ia(pergunta, resposta)
    
    def _extrair_contexto_ia(self, pergunta, resposta):
        """
        Usa IA para extrair informações relevantes da conversa.
        """
        try:
            # Construir prompt para extração
            prompt = f"""
            Analise a conversa abaixo e extraia informações relevantes para uma consulta SQL.
            
            Pergunta do usuário: "{pergunta}"
            Resposta da IA: "{resposta[:200]}..."
            
            Extraia e retorne APENAS um JSON com os campos que encontrar:
            - cidade (nome da cidade, se mencionada)
            - estado (UF, se mencionado)
            - status ('A' para ativo, 'I' para inativo, se mencionado)
            - nome (nome de pessoa, se mencionado)
            - cep (CEP, se mencionado)
            - bairro (bairro, se mencionado)
            
            Exemplo de resposta:
            {{"cidade": "SÃO PAULO", "estado": "SP", "status": "A"}}
            
            Se não encontrar nada, retorne: {{}}
            """
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Você é um extrator de informações. Retorne apenas JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            # Extrair o JSON da resposta
            texto = response.choices[0].message.content.strip()
            
            # Limpar markdown e texto extra
            texto = re.sub(r'```json\n?', '', texto)
            texto = re.sub(r'```\n?', '', texto)
            texto = texto.strip()
            
            # Tentar fazer parse do JSON
            try:
                novos_contextos = json.loads(texto)
                if isinstance(novos_contextos, dict):
                    # Mesclar com contexto existente (não sobrescrever se vazio)
                    for key, value in novos_contextos.items():
                        if value and value != '':
                            self.contexto[key] = value
                    logger.info(f"📊 Contexto extraído: {self.contexto}")
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Não foi possível parsear JSON: {texto[:100]}")
                
        except Exception as e:
            logger.error(f"❌ Erro ao extrair contexto com IA: {e}")
            # Fallback: extração simples com regex
            self._extrair_contexto_regex(pergunta)
    
    def _extrair_contexto_regex(self, pergunta):
        """
        Método fallback para extrair contexto usando regex.
        Apenas para casos onde a IA falha.
        """
        # Extrair estado (UF)
        estados = re.findall(r'\b(SP|RJ|MG|BA|PE|CE|PR|RS|AM|PA|GO|DF|SC|ES|RN|PB|MA|PI|AL|SE|MT|MS|RO|TO|AC|AP|RR)\b', pergunta.upper())
        if estados and 'estado' not in self.contexto:
            self.contexto['estado'] = estados[0]
        
        # Extrair status
        if 'ativo' in pergunta.lower() and 'status' not in self.contexto:
            self.contexto['status'] = 'A'
        elif 'inativo' in pergunta.lower() and 'status' not in self.contexto:
            self.contexto['status'] = 'I'
    
    def get_contexto(self):
        """Retorna o contexto atual para usar nas próximas perguntas"""
        return self.contexto.copy()
    
    def get_historico_texto(self):
        """Retorna o histórico formatado como texto"""
        if not self.historico:
            return ""
        
        texto = "Histórico da conversa (mantenha este contexto):\n"
        for i, item in enumerate(self.historico[-3:], 1):
            texto += f"{i}. Usuário: {item['pergunta']}\n"
        return texto
    
    def limpar(self):
        """Limpa o contexto e histórico"""
        self.historico = []
        self.contexto = {}
        self._ultima_pergunta = None
        self._ultima_resposta = None
    
    def get_contexto_texto(self):
        """Retorna o contexto como texto para usar no prompt"""
        if not self.contexto:
            return ""
        
        texto = "\nContexto ativo (já mencionado anteriormente):\n"
        for key, value in self.contexto.items():
            if key == 'status':
                status_texto = 'Ativo' if value == 'A' else 'Inativo'
                texto += f"- Status: {status_texto}\n"
            elif key == 'estado':
                texto += f"- Estado: {value}\n"
            elif key == 'cidade':
                texto += f"- Cidade: {value}\n"
            elif key == 'bairro':
                texto += f"- Bairro: {value}\n"
            elif key == 'nome':
                texto += f"- Nome: {value}\n"
            else:
                texto += f"- {key}: {value}\n"
        return texto

# Criar um dicionário para armazenar conversas por sessão
_conversas = {}

def get_conversa(session_id):
    """Obtém ou cria uma conversa para a sessão"""
    if session_id not in _conversas:
        _conversas[session_id] = ConversaContexto()
    return _conversas[session_id]

def limpar_conversa(session_id):
    """Limpa a conversa da sessão"""
    if session_id in _conversas:
        _conversas[session_id].limpar()
        del _conversas[session_id]