# ПРАКТИЧЕСКОЕ ЗАНЯТИЕ № 1
# Разработка REST API для AI-сервиса на FastAPI

import time
import uuid
import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

# Импорты из наших модулей
from schemas import (
    FarmRequest,
    PredictionResponse,
    HealthResponse,
    ModelInfoResponse,
    VersionResponse,
)
from model import calculate_risk
from services import (
    MODEL_NAME,
    MODEL_VERSION,
    MODEL_TYPE,
    MODEL_READY,
    ALLOWED_REGIONS,
    get_risk_level,
    get_recommendation,
)
import storage


# ────────────────────────────────────────────────────────────
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# FASTAPI-ПРИЛОЖЕНИЕ
# ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Agro Scoring API",
    description="REST API для оценки риска сельскохозяйственных предприятий.",
    version="1.0.0",
)


# ────────────────────────────────────────────────────────────
# MIDDLEWARE — измеряем время обработки запроса
# ────────────────────────────────────────────────────────────

@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(round(process_time, 6))
    return response


# ────────────────────────────────────────────────────────────
# ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК (500)
# ────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Ловит любые необработанные исключения и возвращает 500,
    не раскрывая детали клиенту. Полная информация пишется в лог.
    """
    logger.error(
        "Internal error | path=%s | error=%s",
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════


# ────────────────────────────────────────────────────────────
# GET /health — проверка работоспособности API
# ────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Monitoring"],
    summary="Проверка состояния API",
    description="Используется для проверки того, что REST API запущен и отвечает.",
)
def health():
    return {"status": "ok"}


# ────────────────────────────────────────────────────────────
# GET /version — версия API и модели
# ────────────────────────────────────────────────────────────

@app.get(
    "/version",
    response_model=VersionResponse,
    tags=["Monitoring"],
    summary="Версия API и модели",
    description="Возвращает информацию о версии API, модели и дате сборки.",
)
def version():
    return {
        "api_version": "1.0.0",
        "model_version": MODEL_VERSION,
        "build": "2026-10-03",
    }


# ────────────────────────────────────────────────────────────
# GET /model-info — информация о модели
# ────────────────────────────────────────────────────────────

@app.get(
    "/model-info",
    response_model=ModelInfoResponse,
    tags=["Model Info"],
    summary="Информация о модели",
    description="Возвращает название, версию, тип и текущее состояние модели.",
)
def model_info():
    model_status = "ready" if MODEL_READY else "unavailable"
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_type": MODEL_TYPE,
        "status": model_status,
    }


# ────────────────────────────────────────────────────────────
# POST /predict — оценка риска хозяйства
# ────────────────────────────────────────────────────────────

@app.post(
    "/predict",
    response_model=PredictionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Predictions"],
    summary="Оценить риск хозяйства",
    description=(
        "Принимает характеристики хозяйства, выполняет валидацию, "
        "инференс модели и возвращает оценку риска. "
        "Создаёт новую запись прогноза, доступную по /predictions/{request_id}."
    ),
)
def predict(request: FarmRequest):
    # 1. Проверка состояния модели
    if not MODEL_READY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is temporarily unavailable",
        )

    # 2. Бизнес-валидация
    if request.region not in ALLOWED_REGIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown region: {request.region}. "
                f"Allowed regions: {sorted(ALLOWED_REGIONS)}"
            ),
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
        "model_version": MODEL_VERSION,
    }

    # 6. Сохранение результата и исходного запроса
    storage.save_prediction(request_id, result)
    storage.save_original_request(request_id, request.model_dump())

    logger.info(
        "Prediction completed | request_id=%s | farm_id=%s | "
        "risk_score=%s | risk_level=%s",
        request_id,
        request.farm_id,
        score,
        level,
    )

    return result


# ────────────────────────────────────────────────────────────
# GET /predictions — список прогнозов с фильтрацией
# ────────────────────────────────────────────────────────────

@app.get(
    "/predictions",
    response_model=List[PredictionResponse],
    tags=["Predictions"],
    summary="Получить список прогнозов",
    description=(
        "Возвращает список выполненных прогнозов. "
        "Поддерживает ограничение количества и фильтрацию по уровню риска."
    ),
)
def get_predictions(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Максимальное количество результатов",
    ),
    risk_level: Optional[str] = Query(
        default=None,
        description="Фильтр по категории риска: low, medium или high",
    ),
):
    allowed_levels = {"low", "medium", "high"}
    if risk_level is not None and risk_level not in allowed_levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="risk_level must be 'low', 'medium' or 'high'",
        )

    return storage.get_predictions_list(limit, risk_level)


# ────────────────────────────────────────────────────────────
# GET /predictions/{request_id} — прогноз по ID
# ────────────────────────────────────────────────────────────

@app.get(
    "/predictions/{request_id}",
    response_model=PredictionResponse,
    tags=["Predictions"],
    summary="Получить прогноз по request_id",
    description="Возвращает сохранённый прогноз по его уникальному идентификатору.",
)
def get_prediction(request_id: str):
    prediction = storage.get_prediction_by_id(request_id)
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )
    return prediction


# ────────────────────────────────────────────────────────────
# GET /farms/{farm_id}/predictions — история по хозяйству
# ────────────────────────────────────────────────────────────

@app.get(
    "/farms/{farm_id}/predictions",
    response_model=List[PredictionResponse],
    tags=["Predictions"],
    summary="История прогнозов по farm_id",
    description="Возвращает список прогнозов для указанного хозяйства.",
)
def get_farm_history(
    farm_id: str,
    limit: int = Query(10, ge=1, le=100, description="Максимум результатов"),
):
    history = storage.get_by_farm_id(farm_id, limit)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No predictions for farm {farm_id}",
        )
    return history


# ────────────────────────────────────────────────────────────
# GET /predictions/{request_id}/explain — объяснение решения
# ────────────────────────────────────────────────────────────

@app.get(
    "/predictions/{request_id}/explain",
    tags=["Explainability"],
    summary="Объяснение факторов риска",
    description="Возвращает факторы, повлиявшие на итоговую оценку риска.",
)
def explain_prediction(request_id: str):
    prediction = storage.get_prediction_by_id(request_id)
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )

    original = storage.get_original_request(request_id)
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original request not found",
        )

    factors = []
    if original["payment_delay_days"] > 30:
        factors.append(
            {
                "factor": "payment_delay_days",
                "impact": "+0.3",
                "reason": "Просрочка > 30 дней",
            }
        )
    if original["previous_defaults"] > 0:
        factors.append(
            {
                "factor": "previous_defaults",
                "impact": "+0.3",
                "reason": "Наличие прошлых дефолтов",
            }
        )
    if original["debt"] > 5_000_000:
        factors.append(
            {
                "factor": "debt",
                "impact": "+0.2",
                "reason": "Задолженность > 5 млн",
            }
        )
    if original["precipitation_mm"] < 100:
        factors.append(
            {
                "factor": "precipitation_mm",
                "impact": "+0.1",
                "reason": "Мало осадков",
            }
        )

    return {
        "request_id": request_id,
        "final_score": prediction["risk_score"],
        "base_score": 0.1,
        "contributing_factors": factors,
    }


# ────────────────────────────────────────────────────────────
# DELETE /predictions/{request_id} — удаление прогноза
# ────────────────────────────────────────────────────────────

@app.delete(
    "/predictions/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Predictions"],
    summary="Удалить прогноз по request_id",
    description="Удаляет сохранённый прогноз по его идентификатору.",
)
def delete_prediction(request_id: str):
    if not storage.delete_prediction(request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found",
        )
    return None


# ────────────────────────────────────────────────────────────
# ЗАПУСК (для локальной разработки)
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)