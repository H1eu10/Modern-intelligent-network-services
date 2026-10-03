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