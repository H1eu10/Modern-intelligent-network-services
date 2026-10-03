import time
import uuid
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

# Импорты из наших модулей
from schemas import FarmRequest, PredictionResponse, HealthResponse, ModelInfoResponse
from model import calculate_risk
from services import (
    MODEL_NAME, MODEL_VERSION, MODEL_TYPE, MODEL_READY, 
    ALLOWED_REGIONS, get_risk_level, get_recommendation
)
from storage import save_prediction, get_prediction_by_id, get_predictions_list

# НАСТРОЙКА ЛОГИРОВАНИЯ
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# FASTAPI-ПРИЛОЖЕНИЕ
app = FastAPI(
    title="Agro Scoring API",
    description="REST API для оценки риска сельскохозяйственных предприятий.",
    version="1.0.0"
)

# MIDDLEWARE
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 6))
    return response

# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК (500)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Ловит любые необработанные исключения и возвращает
    500 Internal Server Error, не раскрывая детали клиенту.
    Полная информация пишется в лог.
    """
    logger.error(
        "Internal error | path=%s | error=%s",
        request.url.path,
        str(exc)
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

# ENDPOINTS
@app.get("/health", response_model=HealthResponse, tags=["Monitoring"], summary="Проверка состояния API")
def health():
    return {"status": "ok"}

@app.get("/model-info", response_model=ModelInfoResponse, tags=["Model Info"], summary="Информация о модели")
def model_info():
    model_status = "ready" if MODEL_READY else "unavailable"
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_type": MODEL_TYPE,
        "status": model_status
    }

@app.post("/predict", response_model=PredictionResponse, status_code=status.HTTP_201_CREATED, tags=["Predictions"], summary="Оценить риск хозяйства")
def predict(request: FarmRequest):
    # 1. Проверка состояния модели
    if not MODEL_READY:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model is temporarily unavailable")

    # 2. Бизнес-валидация
    if request.region not in ALLOWED_REGIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown region: {request.region}. Allowed regions: {sorted(ALLOWED_REGIONS)}"
        )

    logger.info("Prediction request received | farm_id=%s", request.farm_id)

    # 3. Инференс
    score = calculate_risk(request)

    # 4. Постпроцессинг
    level = get_risk_level(score)
    rec = get_recommendation(level)

    # 5. Формирование результата
    request_id = str(uuid.uuid4())
    result = {
        "request_id": request_id,
        "farm_id": request.farm_id,
        "risk_score": score,
        "risk_level": level,
        "recommendation": rec,
        "model_version": MODEL_VERSION
    }

    # 6. Сохранение
    save_prediction(request_id, result)
    
    logger.info("Prediction completed | request_id=%s | farm_id=%s | risk_score=%s | risk_level=%s", 
                request_id, request.farm_id, score, level)

    return result

@app.get("/predictions", response_model=List[PredictionResponse], tags=["Predictions"], summary="Получить список прогнозов")
def get_predictions(
    limit: int = Query(default=10, ge=1, le=100, description="Максимальное количество результатов"),
    risk_level: Optional[str] = Query(default=None, description="Фильтр по категории риска: low, medium или high")
):
    allowed_levels = {"low", "medium", "high"}
    if risk_level is not None and risk_level not in allowed_levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="risk_level must be 'low', 'medium' or 'high'"
        )
    
    return get_predictions_list(limit, risk_level)

@app.get("/predictions/{request_id}", response_model=PredictionResponse, tags=["Predictions"], summary="Получить прогноз по request_id")
def get_prediction(request_id: str):
    prediction = get_prediction_by_id(request_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prediction not found")
    return prediction

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)