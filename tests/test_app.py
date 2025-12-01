# tests/test_app.py

from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import patch, MagicMock
import os
# Importar a função principal de agendamento (ajuste o import se o código estiver em outro arquivo)
from app import agendar_mensagem, app 

# --- FIXTURES (Preparação do Teste) ---

@pytest.fixture
def client():
    """Fixture para cliente de teste do Flask."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# --- TESTES DE UNIDADE PARA VALIDAÇÃO ---

# O decorator @patch substitui a função real store_message por um Mock
@patch('app.store_message', return_value='fake-uuid-123') 
@patch.dict(os.environ, {'DYNAMODB_TABLE_NAME': 'TestTable'})
def test_agendamento_sucesso(mock_store):
    """Testa o agendamento de uma mensagem com dados válidos."""
    
    # 10 minutos no futuro (em UTC)
    data_futura = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    conteudo = "Esta é uma mensagem de teste válida."
    
    # Ação (Act)
    resultado_id = agendar_mensagem(conteudo, data_futura)
    
    # Verificação (Assert)
    assert resultado_id == 'fake-uuid-123'
    # Verifica se a função de armazenamento foi chamada
    mock_store.assert_called_once()


# Teste para data no passado
@patch('app.store_message')
@patch.dict(os.environ, {'DYNAMODB_TABLE_NAME': 'TestTable'})
def test_data_passada_falha(mock_store):
    """Deve falhar ao tentar agendar uma data no passado."""
    data_passada = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    conteudo = "Mensagem com data inválida"
    
    with pytest.raises(ValueError) as excinfo:
        agendar_mensagem(conteudo, data_passada)
        
    assert "data de envio deve ser no futuro" in str(excinfo.value)
    mock_store.assert_not_called() # Não deve tentar salvar


# Teste para mensagem vazia
@patch('app.store_message')
@patch.dict(os.environ, {'DYNAMODB_TABLE_NAME': 'TestTable'})
def test_conteudo_vazio_falha(mock_store):
    """Deve falhar com conteúdo vazio."""
    data_futura = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    
    with pytest.raises(ValueError) as excinfo:
        agendar_mensagem("  ", data_futura) # Espaços vazios
        
    assert "conteúdo da mensagem não pode ser vazio" in str(excinfo.value)
    mock_store.assert_not_called()


# --- TESTES DE INTEGRAÇÃO DO ENDPOINT (Controller) ---

# Mocka a função de agendamento para testar apenas o endpoint Flask
@patch('app.agendar_mensagem', return_value='endpoint-uuid-456') 
def test_schedule_endpoint_sucesso(mock_agendar, client):
    """Testa se o endpoint /schedule retorna 201 com sucesso."""
    
    response = client.post(
        '/schedule', 
        json={
            "content": "Testando via API", 
            "send_date": "2026-06-01T10:00:00+00:00"
        }
    )
    
    assert response.status_code == 201
    data = response.get_json()
    assert data['status'] == 'success'
    assert data['id'] == 'endpoint-uuid-456'
    mock_agendar.assert_called_once()