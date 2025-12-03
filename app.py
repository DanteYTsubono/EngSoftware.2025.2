from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import boto3
import os
import uuid
import re
from zoneinfo import ZoneInfo # Import necessário para lidar com fusos horários de forma correta

# --- CONFIGURAÇÃO E INICIALIZAÇÃO ---

app = Flask(__name__)

# Configuração do DynamoDB
DYNAMODB_CLIENT = boto3.resource('dynamodb', 
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'FutureMessages') 

# Fuso Horário de Brasília para exibir mensagens de erro mais amigáveis ao usuário
BRASILIA_TZ = ZoneInfo('America/Sao_Paulo') 

# --- MODEL (Lógica de Negócio) ---

def get_messages_table():
    """Retorna o objeto da tabela DynamoDB."""
    try:
        # O boto3 usa as VAs AWS_ACCESS_KEY_ID e AWS_SECRET_ACCESS_KEY daqui
        return DYNAMODB_CLIENT.Table(TABLE_NAME)
    except Exception as e:
        # Se as chaves estiverem erradas ou a região incorreta, o erro de autenticação ocorre aqui.
        print(f"Erro ao obter a tabela DynamoDB: {e}")
        return None

def store_message(email_address: str, conteudo: str, data_envio: datetime):
    """Armazena o item no DynamoDB."""
    table = get_messages_table()
    if not table:
        raise Exception("Falha na conexão ou acesso ao banco de dados. (Verificar credenciais AWS).")

    # Gera um ID único para a chave primária
    message_id = str(uuid.uuid4())
    
    item = {
        'id': message_id,
        'email_address': email_address, # Novo campo para o endereço de e-mail
        'content': conteudo,
        'send_date': data_envio.isoformat(), # MANTIDO EM UTC PARA CONSISTÊNCIA INTERNACIONAL
        'status': 'PENDING'
    }
    
    # Salva o item
    table.put_item(Item=item)
    return message_id

def agendar_mensagem(email_address: str, conteudo: str, data_envio_str: str) -> str:
    """
    Função principal do Model: valida e armazena o email futuro.
    """
    # 1. Validação de Email (Regex simples para e-mail)
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_address):
         raise ValueError("O endereço de e-mail é inválido.")
         
    # 2. Validação de Conteúdo
    if not conteudo or len(conteudo.strip()) == 0:
        raise ValueError("O conteúdo do e-mail não pode ser vazio.")
    # Removida a limitação de 4096 caracteres, já que e-mails não têm essa restrição do WhatsApp.

    # 3. Validação da Data
    try:
        data_envio = datetime.fromisoformat(data_envio_str)
        # Se a data não tiver fuso horário (ex: '2025-12-03T20:00:00'), assume-se UTC
        if data_envio.tzinfo is None or data_envio.tzinfo.utcoffset(data_envio) is None:
             data_envio = data_envio.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("Formato de data e hora inválido. Use formato ISO 8601 (ex: YYYY-MM-DDTHH:MM:SS+00:00).")
        
    # Deve ser no mínimo 1 minuto no futuro (em UTC)
    tempo_minimo = datetime.now(timezone.utc) + timedelta(minutes=1)

    if data_envio <= tempo_minimo:
        # Conversão para Brasília APENAS para a mensagem de erro que vai para o usuário
        tempo_minimo_brasilia = tempo_minimo.astimezone(BRASILIA_TZ).strftime('%Y-%m-%d %H:%M:%S')
        raise ValueError(f"A data de envio deve ser no futuro. O horário mínimo é: {tempo_minimo_brasilia} (Horário de Brasília).")
        
    # 4. Armazenamento
    return store_message(email_address, conteudo, data_envio)

# --- CONTROLLER (Rotas Flask) ---

@app.route('/', methods=['GET'])
def home():
    """Rota raiz para confirmar que a API está ativa."""
    return "Email Scheduler API está rodando e pronta para receber agendamentos via POST /schedule.", 200

@app.route('/schedule', methods=['POST'])
def schedule_message():
    """Endpoint para agendar o email via API."""
    data = request.get_json()
    
    # Campo esperado no JSON: email_address, content, send_date
    email_address = data.get('email_address') 
    conteudo = data.get('content')
    data_envio = data.get('send_date')

    try:
        message_id = agendar_mensagem(email_address, conteudo, data_envio) 
        
        return jsonify({
            "status": "success", 
            "message": "Email agendado com sucesso.",
            "id": message_id
        }), 201
    except ValueError as e:
        # Erros de validação retornam 400 Bad Request
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        # Erros internos (principalmente falha de conexão AWS) retornam 500 Internal Error
        print(f"ERRO INTERNO CRÍTICO NA REQUISIÇÃO: {e}", flush=True)
        return jsonify({"status": "error", "message": "Erro interno ao processar a requisição. (Verificar logs do Heroku para detalhes do AWS/DynamoDB). "}), 500

if __name__ == '__main__':
    # Usado para rodar localmente
    app.run(debug=True)