# app.py

from flask import Flask, request, jsonify
from datetime import datetime, timezone, timedelta
import boto3
import os
import uuid

# --- CONFIGURAÇÃO E INICIALIZAÇÃO ---

app = Flask(__name__)

# Configuração do DynamoDB
# Assume que você definiu DYNAMODB_TABLE_NAME como variável de ambiente
DYNAMODB_CLIENT = boto3.resource('dynamodb', 
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)
TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'FutureMessages') 

# --- MODEL (Lógica de Negócio) ---

def get_messages_table():
    """Retorna o objeto da tabela DynamoDB."""
    try:
        # A criação da tabela é feita fora do código (via AWS Console/IaC)
        return DYNAMODB_CLIENT.Table(TABLE_NAME)
    except Exception as e:
        # Em um ambiente de produção, logar este erro
        print(f"Erro ao obter a tabela DynamoDB: {e}")
        return None

def store_message(conteudo: str, data_envio: datetime):
    """Armazena o item no DynamoDB."""
    table = get_messages_table()
    if not table:
        raise Exception("Falha na conexão ou acesso ao banco de dados.")

    # Gera um ID único para a chave primária
    message_id = str(uuid.uuid4())
    
    item = {
        'id': message_id,
        'content': conteudo,
        'send_date': data_envio.isoformat(), # Armazenado em formato ISO
        'status': 'PENDING'
    }
    
    # Salva o item
    table.put_item(Item=item)
    return message_id

def agendar_mensagem(conteudo: str, data_envio_str: str) -> str:
    """
    Função principal do Model: valida e armazena a mensagem futura.
    """
    # 1. Validação de Conteúdo
    if not conteudo or len(conteudo.strip()) == 0:
        raise ValueError("O conteúdo da mensagem não pode ser vazio.")
    if len(conteudo) > 4096:
        raise ValueError("A mensagem excede o limite de 4096 caracteres do WhatsApp.")

    # 2. Validação da Data
    try:
        # Ponto Crucial: Armazenamos datas no DynamoDB como ISO strings
        # O timezone 'Z' (UTC) é a melhor prática para armazenamento de datas
        data_envio = datetime.fromisoformat(data_envio_str)
        # Se não tiver informação de timezone, assume-se que é UTC (melhor para o scheduler)
        if data_envio.tzinfo is None or data_envio.tzinfo.utcoffset(data_envio) is None:
             data_envio = data_envio.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError("Formato de data e hora inválido. Use formato ISO 8601 (ex: YYYY-MM-DDTHH:MM:SS+00:00).")
        
    # Deve ser pelo menos 1 minuto no futuro para dar tempo de processamento
    tempo_minimo = datetime.now(timezone.utc) + timedelta(minutes=1)

    if data_envio <= tempo_minimo:
        raise ValueError("A data de envio deve ser no futuro.")
        
    # 3. Armazenamento
    return store_message(conteudo, data_envio)

# --- CONTROLLER (Rotas Flask) ---

@app.route('/', methods=['GET'])
def home():
    """Rota raiz para confirmar que a API está ativa."""
    return "WhatsApp Scheduler API está rodando e pronta para receber agendamentos

@app.route('/schedule', methods=['POST'])
def schedule_message():
    """Endpoint para agendar a mensagem via API."""
    data = request.get_json()
    conteudo = data.get('content')
    data_envio = data.get('send_date')

    try:
        message_id = agendar_mensagem(conteudo, data_envio)
        return jsonify({
            "status": "success", 
            "message": "Mensagem agendada com sucesso.",
            "id": message_id
        }), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception:
        # Tratar erros de DynamoDB ou outros erros internos
        return jsonify({"status": "error", "message": "Erro interno ao processar a requisição."}), 500

if __name__ == '__main__':
    # Usado para rodar localmente (necessário ter o DynamoDB local ou simulação)
    app.run(debug=True)