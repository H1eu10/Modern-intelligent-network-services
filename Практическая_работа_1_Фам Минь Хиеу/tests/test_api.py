"""
Автоматические тесты для Agro Scoring API.
Запуск: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ─────────────────────────────────────────────────────────────
# ФИКСТУРЫ (общие тестовые данные)
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def valid_payload():
    """Валидный запрос для /predict"""
    return {
        "farm_id": "FARM-TEST-001",
        "region": "Krasnodar",
        "crop_type": "wheat",
        "area_ha": 2500,
        "temperature_avg": 24.3,
        "precipitation_mm": 320,
        "payment_delay_days": 45,
        "previous_defaults": 1,
        "debt": 6500000,
    }


@pytest.fixture
def low_risk_payload():
    """Запрос без факторов риска — должен дать 'low'"""
    return {
        "farm_id": "FARM-TEST-LOW",
        "region": "Rostov",
        "crop_type": "corn",
        "area_ha": 100,
        "temperature_avg": 20.0,
        "precipitation_mm": 500,
        "payment_delay_days": 0,
        "previous_defaults": 0,
        "debt": 100000,
    }


@pytest.fixture
def created_prediction(valid_payload):
    """Создаёт прогноз и возвращает его request_id"""
    response = client.post("/predict", json=valid_payload)
    assert response.status_code == 201
    return response.json()["request_id"]


# ─────────────────────────────────────────────────────────────
# 1. GET /health
# ─────────────────────────────────────────────────────────────

def test_health_returns_200():
    """GET /health → 200 + {status: ok}"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ─────────────────────────────────────────────────────────────
# 2. GET /model-info
# ─────────────────────────────────────────────────────────────

def test_model_info_returns_200():
    """GET /model-info → 200 + все обязательные поля"""
    response = client.get("/model-info")
    assert response.status_code == 200
    data = response.json()
    assert data["model_name"] == "agro-risk-model"
    assert data["model_version"] == "1.0"
    assert data["model_type"] == "risk-scoring"
    assert data["status"] == "ready"


# ─────────────────────────────────────────────────────────────
# 3. GET /version
# ─────────────────────────────────────────────────────────────

def test_version_returns_200():
    """GET /version → 200 + api_version/model_version/build"""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "api_version" in data
    assert "model_version" in data
    assert "build" in data


# ─────────────────────────────────────────────────────────────
# 4. POST /predict — успешные сценарии
# ─────────────────────────────────────────────────────────────

def test_predict_high_risk_returns_201(valid_payload):
    """POST /predict (много факторов риска) → 201 + level='high'"""
    response = client.post("/predict", json=valid_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["risk_level"] == "high"
    assert data["risk_score"] >= 0.7
    assert data["farm_id"] == valid_payload["farm_id"]
    assert "request_id" in data
    assert data["model_version"] == "1.0"


def test_predict_low_risk_returns_201(low_risk_payload):
    """POST /predict (нет факторов риска) → level='low'"""
    response = client.post("/predict", json=low_risk_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["risk_level"] == "low"
    assert data["risk_score"] < 0.3


def test_predict_returns_valid_uuid(valid_payload):
    """request_id должен быть UUID v4"""
    import uuid
    response = client.post("/predict", json=valid_payload)
    request_id = response.json()["request_id"]
    # Если невалидный UUID — бросит ValueError
    uuid.UUID(request_id, version=4)


# ─────────────────────────────────────────────────────────────
# 5. POST /predict — ошибки валидации (422)
# ─────────────────────────────────────────────────────────────

def test_predict_invalid_area_returns_422(valid_payload):
    """area_ha = -100 → 422 (Pydantic)"""
    payload = {**valid_payload, "area_ha": -100}
    response = client.post("/predict", json=payload)
    assert response.status_code == 422


def test_predict_missing_field_returns_422(valid_payload):
    """Отсутствует обязательное поле → 422"""
    payload = dict(valid_payload)
    del payload["region"]
    response = client.post("/predict", json=payload)
    assert response.status_code == 422


def test_predict_wrong_type_returns_422(valid_payload):
    """area_ha = 'abc' → 422"""
    payload = {**valid_payload, "area_ha": "abc"}
    response = client.post("/predict", json=payload)
    assert response.status_code == 422


def test_predict_temperature_out_of_range_returns_422(valid_payload):
    """temperature_avg = 100 → 422 (максимум 60)"""
    payload = {**valid_payload, "temperature_avg": 100}
    response = client.post("/predict", json=payload)
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# 6. POST /predict — бизнес-валидация (400)
# ─────────────────────────────────────────────────────────────

def test_predict_unknown_region_returns_400(valid_payload):
    """region = 'Moscow' → 400 (бизнес-правило)"""
    payload = {**valid_payload, "region": "Moscow"}
    response = client.post("/predict", json=payload)
    assert response.status_code == 400
    assert "Unknown region" in response.json()["detail"]


# ─────────────────────────────────────────────────────────────
# 7. GET /predictions/{request_id}
# ─────────────────────────────────────────────────────────────

def test_get_existing_prediction_returns_200(created_prediction):
    """GET /predictions/{id} — существующий → 200"""
    response = client.get(f"/predictions/{created_prediction}")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == created_prediction


def test_get_unknown_prediction_returns_404():
    """GET /predictions/nonexistent → 404"""
    response = client.get("/predictions/nonexistent-id-12345")
    assert response.status_code == 404
    assert response.json()["detail"] == "Prediction not found"


# ─────────────────────────────────────────────────────────────
# 8. GET /predictions — список + фильтрация + лимит
# ─────────────────────────────────────────────────────────────

def test_predictions_list_returns_200():
    """GET /predictions → 200 + список"""
    response = client.get("/predictions")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_predictions_limit_works(valid_payload):
    """GET /predictions?limit=2 → максимум 2 записи"""
    for i in range(5):
        client.post("/predict", json={**valid_payload, "farm_id": f"FARM-{i}"})
    response = client.get("/predictions?limit=2")
    assert response.status_code == 200
    assert len(response.json()) <= 2


def test_predictions_filter_by_risk_level(valid_payload, low_risk_payload):
    """GET /predictions?risk_level=high → только high"""
    client.post("/predict", json=valid_payload)        # high
    client.post("/predict", json=low_risk_payload)     # low
    response = client.get("/predictions?risk_level=high")
    assert response.status_code == 200
    for item in response.json():
        assert item["risk_level"] == "high"


def test_predictions_invalid_risk_level_returns_400():
    """GET /predictions?risk_level=extreme → 400"""
    response = client.get("/predictions?risk_level=extreme")
    assert response.status_code == 400


def test_predictions_limit_negative_returns_422():
    """GET /predictions?limit=-5 → 422"""
    response = client.get("/predictions?limit=-5")
    assert response.status_code == 422


def test_predictions_limit_too_large_returns_422():
    """GET /predictions?limit=999 → 422 (максимум 100)"""
    response = client.get("/predictions?limit=999")
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# 9. GET /farms/{farm_id}/predictions — ИСТОРИЯ ПО ХОЗЯЙСТВУ
# ─────────────────────────────────────────────────────────────

def test_farm_history_returns_200(valid_payload):
    """GET /farms/{id}/predictions — существующий farm_id → 200"""
    farm_id = "FARM-HISTORY-001"
    # Создаём 3 прогноза для одного хозяйства
    for _ in range(3):
        client.post("/predict", json={**valid_payload, "farm_id": farm_id})
    
    response = client.get(f"/farms/{farm_id}/predictions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 3
    for item in data:
        assert item["farm_id"] == farm_id


def test_farm_history_respects_limit(valid_payload):
    """GET /farms/{id}/predictions?limit=1 → максимум 1 запись"""
    farm_id = "FARM-HISTORY-LIMIT"
    for _ in range(5):
        client.post("/predict", json={**valid_payload, "farm_id": farm_id})
    
    response = client.get(f"/farms/{farm_id}/predictions?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_farm_history_unknown_farm_returns_404():
    """GET /farms/unknown-farm/predictions → 404"""
    response = client.get("/farms/unknown-farm-xyz/predictions")
    assert response.status_code == 404


def test_farm_history_invalid_limit_returns_422():
    """GET /farms/{id}/predictions?limit=-1 → 422"""
    response = client.get("/farms/FARM-001/predictions?limit=-1")
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# 10. GET /predictions/{request_id}/explain — ОБЪЯСНЕНИЕ
# ─────────────────────────────────────────────────────────────

def test_explain_high_risk_returns_200(created_prediction):
    """GET /predictions/{id}/explain → 200 + contributing_factors"""
    response = client.get(f"/predictions/{created_prediction}/explain")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == created_prediction
    assert "final_score" in data
    assert "base_score" in data
    assert "contributing_factors" in data
    assert isinstance(data["contributing_factors"], list)


def test_explain_high_risk_has_factors(created_prediction):
    """Для high-risk прогноза должны быть факторы"""
    response = client.get(f"/predictions/{created_prediction}/explain")
    data = response.json()
    # В нашем тестовом payload — 4 фактора риска
    assert len(data["contributing_factors"]) > 0
    # Каждый фактор имеет обязательные поля
    for factor in data["contributing_factors"]:
        assert "factor" in factor
        assert "impact" in factor
        assert "reason" in factor


def test_explain_low_risk_has_no_factors(low_risk_payload):
    """Для low-risk прогноза факторов не должно быть"""
    r = client.post("/predict", json=low_risk_payload)
    request_id = r.json()["request_id"]
    
    response = client.get(f"/predictions/{request_id}/explain")
    assert response.status_code == 200
    data = response.json()
    # Нет факторов — только базовый score
    assert data["final_score"] == data["base_score"]
    assert data["contributing_factors"] == []


def test_explain_unknown_prediction_returns_404():
    """GET /predictions/unknown/explain → 404"""
    response = client.get("/predictions/unknown-id-xyz/explain")
    assert response.status_code == 404


# ─────────────────────────────────────────────────────────────
# 11. Проверка заголовка X-Process-Time (middleware)
# ─────────────────────────────────────────────────────────────

def test_process_time_header_present():
    """Все ответы должны содержать X-Process-Time"""
    response = client.get("/health")
    assert "x-process-time" in response.headers
    # Значение должно быть числом
    float(response.headers["x-process-time"])