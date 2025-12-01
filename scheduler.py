# scheduler.py

import boto3
from boto3.dynamodb.conditions import Key
import os
import time
from datetime import datetime, timezone
import requests

# --- CONFIGURAÇÃO ---
# Certifique-se de que estas variáveis de ambiente (ou secrets) estão configuradas 
# para o seu ambiente de deploy (AWS Lambda ou Heroku Worker)
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME', 'FutureMessages')
WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN')

# Configuração do DynamoDB e WhatsApp API
DYNAMODB_CLIENT = boto3.resource('dynamodb', region_name=AWS_REGION)
MESSAGES_TABLE = DYNAMODB_CLIENT.Table(DYNAMODB_TABLE_NAME)

WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN')
WHATSAPP_PHONE_ID = os.environ.get('WHATSAPP_PHONE_ID')

# --- FUNÇÕES DE LÓGICA DE NEGÓCIO ---

def send_whatsapp_message(recipient_number: str, content: str) -> bool:
    """
    Envia a mensagem real usando a Meta WhatsApp Cloud API.
    """
    if not WHATSAPP_API_TOKEN or not WHATSAPP_PHONE_ID:
        print("ERRO DE CONFIGURAÇÃO: TOKEN ou PHONE_ID ausentes. Simulação de sucesso.")
        return True

    # URL do endpoint de envio de mensagem. O formato é padrão da Meta.
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json",
    }
    
    # Payload para enviar uma MENSAGEM DE TEXTO
    payload = {
        "messaging_product": "whatsapp",
        "to": recipient_number.replace('+', ''), 
        "type": "text",
        "text": {
            "body": content
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            print(f"Sucesso no envio para {recipient_number}. ID da Meta: {response.json().get('messages')[0]['id']}")
            return True
        else:
            print(f"Falha na API da Meta. Status: {response.status_code}. Erro: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao enviar para {recipient_number}: {e}")
        return False


def fetch_and_process_messages():
    """
    Busca mensagens pendentes no DynamoDB e tenta enviá-las.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    
    print(f"[{datetime.now().isoformat()}] Buscando mensagens para envio em ou antes de: {now_utc}")

    # Query para buscar itens: 
    # KeyConditionExpression: 'status = :status' -> Isso usa a Chave de Partição
    # FilterExpression: 'send_date <= :now' -> Isso filtra o resultado da Query
    #
    # NOTA: O DynamoDB requer que a KeyCondition use a Chave de Partição (PK)
    # Para buscas por data (que é o que você quer), uma Secondary Index (GSI)
    # com o status como PK e send_date como SK seria mais eficiente.
    # Por enquanto, vamos usar Scan (menos eficiente) ou uma Query bem estruturada.

    try:
        # Usando Scan (fácil de implementar, mas caro/lento em larga escala!)
        response = MESSAGES_TABLE.query(
            IndexName='StatusDateIndex',  # Nome do seu GSI
            KeyConditionExpression=Key('status').eq('PENDING') & Key('send_date').lte(now_utc)
        )
        
        messages = response.get('Items', [])
        print(f"Encontradas {len(messages)} mensagens pendentes.")
        
        for msg in messages:
            try:
                if send_whatsapp_message(msg['recipient'], msg['content']):
                    # Atualiza o status no DynamoDB
                    MESSAGES_TABLE.update_item(
                        Key={'id': msg['id']},
                        UpdateExpression='SET #s = :newStatus',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={':newStatus': 'SENT'}
                    )
                    print(f"✅ Enviado e atualizado: {msg['id']}")
                else:
                    print(f"❌ Falha no envio para: {msg['id']}")
                    # Você poderia adicionar lógica de retry aqui
                    
            except Exception as e:
                print(f"Erro ao processar mensagem {msg['id']}: {e}")

    except Exception as e:
        print(f"ERRO CRÍTICO no Scheduler: Falha ao acessar DynamoDB: {e}")


def scheduler_loop(interval_seconds=60):
    """
    Loop principal do scheduler.
    """
    print("Iniciando o Scheduler...")
    while True:
        fetch_and_process_messages()
        # Aguarda o tempo definido antes da próxima execução
        time.sleep(interval_seconds)


if __name__ == '__main__':
    # Este bloco executa o loop principal
    # No Heroku, este script seria executado por um 'worker' no Procfile
    scheduler_loop()