# Временное хранилище в оперативной памяти
predictions = {}

def save_prediction(request_id: str, result: dict):
    predictions[request_id] = result

def get_prediction_by_id(request_id: str):
    return predictions.get(request_id)

def get_predictions_list(limit: int, risk_level: str = None):
    values = list(predictions.values())
    if risk_level is not None:
        values = [item for item in values if item["risk_level"] == risk_level]
    return values[:limit]

def delete_prediction(request_id: str) -> bool:
    if request_id in predictions:
        del predictions[request_id]
        return True
    return False

# ХРАНИЛИЩЕ ОРИГИНАЛЬНЫХ ЗАПРОСОВ (для explainability)
original_requests = {}

def save_original_request(request_id: str, request_data: dict):
    """Сохраняет исходный запрос для последующего объяснения"""
    original_requests[request_id] = request_data

def get_original_request(request_id: str):
    """Возвращает исходный запрос по request_id"""
    return original_requests.get(request_id)


# ИСТОРИЯ ПО ХОЗЯЙСТВУ
def get_by_farm_id(farm_id: str, limit: int = 10):
    """Возвращает список прогнозов для указанного farm_id"""
    values = [
        item for item in predictions.values()
        if item["farm_id"] == farm_id
    ]
    return values[:limit]