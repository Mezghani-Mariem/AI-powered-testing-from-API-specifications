import pytest
from src.test_runner import validate_test_case

# On crée un faux OpenAPI pour le test
MOCK_OPENAPI = {
    "paths": {
        "/items": {
            "get": {},
            "post": {}
        },
        "/items/{item_id}": {
            "get": {}
        }
    }
}

def test_validation_succes():
    """Un cas valide doit passer la validation."""
    case = {
        "test_id": "TC_001", "name": "Valid", "method": "GET", 
        "endpoint": "/items", "test_type": "positive", 
        "path_params": {}, "query_params": {}, "headers": {}, 
        "body": None, "expected_status": 200
    }
    is_valid, msg = validate_test_case(case, MOCK_OPENAPI)
    assert is_valid is True
    assert msg == "OK"

def test_validation_endpoint_inexistant():
    """Un endpoint absent de l'OpenAPI doit être rejeté."""
    case = {
        "test_id": "TC_002", "name": "Invalid", "method": "GET", 
        "endpoint": "/users", "test_type": "positive", 
        "path_params": {}, "query_params": {}, "headers": {}, 
        "body": None, "expected_status": 200
    }
    is_valid, msg = validate_test_case(case, MOCK_OPENAPI)
    assert is_valid is False
    assert "absent de l'OpenAPI" in msg

def test_validation_type_invalide():
    """Un test_type inconnu doit être rejeté."""
    case = {
        "test_id": "TC_003", "name": "Invalid Type", "method": "GET", 
        "endpoint": "/items", "test_type": "unknown_type", 
        "path_params": {}, "query_params": {}, "headers": {}, 
        "body": None, "expected_status": 200
    }
    is_valid, msg = validate_test_case(case, MOCK_OPENAPI)
    assert is_valid is False
    assert "test_type invalide" in msg