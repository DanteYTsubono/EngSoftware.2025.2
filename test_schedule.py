# test_schedule.py (Adaptado para Email)

import requests
from datetime import datetime, timedelta, timezone
import os

# 🚨 AJUSTE A URL
# Use o nome do seu aplicativo Heroku com o sufixo:
HEROKU_APP_URL = "https://whatsapp-future-message-0f7dd7bec338.herokuapp.com/schedule"

def schedule_test_message():
    """Envia uma mensagem de teste agendada para o endpoint do Heroku."""
    
    # Agendar a mensagem para 3 minutos no futuro
    future_time = datetime.now(timezone.utc) + timedelta(minutes=3)
    data_agendamento = future_time.isoformat()
    
    payload = {
        # 🚨 CAMPO MUDOU! Use um email VÁLIDO para o teste.
        "email_address": "seu.email.de.teste@exemplo.com", 
        "content": f"Teste Final de Email! Mensagem agendada e enviada pelo scheduler. Hora UTC: {future_time.strftime('%H:%M:%S')}.",
        "send_date": data_agendamento
    }
    
    print(f"Tentando agendar para: {data_agendamento}")
    
    try:
        response = requests.post(HEROKU_APP_URL, json=payload)
        
        if response.status_code == 201:
            print("\n✅ SUCESSO NO AGENDAMENTO")
            print(f"Aguarde 3 minutos. O Agendador (worker) deve enviar o email.")
        else:
            print(f"\n❌ FALHA NO AGENDAMENTO (Status {response.status_code})")
            print(f"Erro: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ ERRO DE CONEXÃO: {e}")


if __name__ == '__main__':
    schedule_test_message()