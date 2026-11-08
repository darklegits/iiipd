"""FastAPI-приложение «Погодный оракул»."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlencode

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import (
    ALL_CITIES,
    APP_NAME,
    APP_SUBTITLE,
    ARTIFACT_DIR,
    CITIES,
    MODEL_LABELS,
    MODEL_ORDER,
    STATIC_DIR,
    TEMPLATE_DIR,
)
from .data import DataFetchError
from .service import ArtifactError, WeatherOracleStore
from .sport import build_payload as build_sport_payload

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

PAGE_LABELS = {
    "forecast": "Прогноз",
    "sport": "Спорт",
    "profile": "Личный кабинет",
    "compare": "Сравнение",
    "models": "Модели",
    "method": "Методика",
}


def render_page(request: Request, city: str | None, page: str) -> HTMLResponse:
    store = get_store(request)
    try:
        target = store.get(city)
        context = store.page_context(city)
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Для городов без обученных моделей доступны прогноз, спорт и кабинет.
    if not target.city.get("modeled", True) and page in {"compare", "models", "method"}:
        params = dict(request.query_params)
        params["city"] = str(target.city["slug"])
        return RedirectResponse(url=f"/forecast?{urlencode(params)}", status_code=307)
    context["request"] = request
    context["app_name"] = APP_NAME
    context["app_subtitle"] = APP_SUBTITLE
    context["page"] = page
    context["page_label"] = PAGE_LABELS[page]
    return templates.TemplateResponse(request=request, name="index.html", context=context)


def ru_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{int(digits)}f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(value)


templates.env.filters["ru"] = ru_number


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = WeatherOracleStore()
    yield


app = FastAPI(
    title=APP_NAME,
    description=APP_SUBTITLE,
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/artifacts", StaticFiles(directory=str(ARTIFACT_DIR)), name="artifacts")


def get_store(request: Request) -> WeatherOracleStore:
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Сервис ещё загружается")
    return store


@app.get("/")
async def index(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> RedirectResponse:
    store = get_store(request)
    target = city or store.default_slug
    params = dict(request.query_params)
    params["city"] = target
    return RedirectResponse(url=f"/forecast?{urlencode(params)}", status_code=307)


@app.get("/forecast", response_class=HTMLResponse)
async def page_forecast(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> HTMLResponse:
    return render_page(request, city, "forecast")


@app.get("/sport", response_class=HTMLResponse)
async def page_sport(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> HTMLResponse:
    return render_page(request, city, "sport")


@app.get("/profile", response_class=HTMLResponse)
async def page_profile(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> HTMLResponse:
    return render_page(request, city, "profile")


@app.get("/compare", response_class=HTMLResponse)
async def page_compare(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> HTMLResponse:
    return render_page(request, city, "compare")


@app.get("/models", response_class=HTMLResponse)
async def page_models(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> HTMLResponse:
    return render_page(request, city, "models")


@app.get("/method", response_class=HTMLResponse)
async def page_method(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> HTMLResponse:
    return render_page(request, city, "method")


@app.get("/api/health")
async def health(request: Request) -> dict[str, Any]:
    store = get_store(request)
    default = store.get()
    return {
        "status": "ok",
        "service": APP_NAME,
        "cities_loaded": len(store.cities),
        "cities_catalog": len(ALL_CITIES),
        "models_loaded": sum(city.model_count for city in store.cities.values()),
        "default_city": default.slug,
        "cities": list(store.cities),
        "trained_at": default.metrics.get("generated_at"),
        "test_period": default.metrics.get("periods", {}).get("test"),
        "artifact_errors": store.artifact_errors,
    }


@app.get("/api/cities")
async def api_cities(request: Request) -> JSONResponse:
    store = get_store(request)
    return JSONResponse({"cities": store.catalog(), "default": store.default_slug})


@app.get("/api/metrics")
async def api_metrics(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> JSONResponse:
    store = get_store(request)
    try:
        city_store = store.get(city)
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not city_store.city.get("modeled", True):
        raise HTTPException(
            status_code=404,
            detail="Для этого города нет обученной модели: метрики недоступны.",
        )
    return JSONResponse(city_store.metrics)


@app.get("/api/forecast")
async def api_forecast(
    request: Request,
    city: str | None = Query(None, description="slug города"),
    refresh: bool = Query(False, description="Пропустить кэш и загрузить свежие данные"),
) -> JSONResponse:
    store = get_store(request)
    try:
        payload = store.live_forecast(city, force=refresh)
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataFetchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"Не удалось построить живой прогноз: {exc}"
        ) from exc
    return JSONResponse(payload)


@app.get("/api/sport")
async def api_sport(
    request: Request,
    city: str | None = Query(None, description="slug города"),
) -> JSONResponse:
    store = get_store(request)
    try:
        city_store = store.get(city)
        forecast = city_store.live_forecast()
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DataFetchError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    payload = build_sport_payload(forecast, city_store.city)
    return JSONResponse(payload)


@app.get("/api/backtest")
async def api_backtest(
    request: Request,
    city: str | None = Query(None, description="slug города"),
    lead: int | None = Query(None, ge=1, le=7),
    model: str = Query("ensemble"),
) -> dict[str, Any]:
    store = get_store(request)
    try:
        city_store = store.get(city)
    except ArtifactError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if model not in (*MODEL_ORDER, "ensemble", "official", "persistence"):
        raise HTTPException(status_code=400, detail="Неизвестная модель")
    if not city_store.city.get("modeled", True):
        raise HTTPException(
            status_code=404,
            detail="Для этого города нет обученной модели: бэктест недоступен.",
        )
    frame = city_store.predictions
    if lead is not None:
        frame = frame.loc[frame["lead"] == lead]
    frame = frame.dropna(subset=["fact", model])
    rows = [
        {
            "date": row["date"].date().isoformat(),
            "lead": int(row["lead"]),
            "fact": float(row["fact"]),
            model: None if pd.isna(row[model]) else float(row[model]),
        }
        for _, row in frame.iterrows()
    ]
    return {
        "city": city_store.slug,
        "city_name": city_store.city["name"],
        "model": model,
        "label": MODEL_LABELS.get(model, model),
        "lead": lead,
        "n": len(rows),
        "rows": rows,
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> JSONResponse:
    return JSONResponse(status_code=204, content=None)


@app.get("/manifest.webmanifest", include_in_schema=False)
async def manifest() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.exception_handler(ArtifactError)
async def artifact_error_handler(request: Request, exc: ArtifactError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})
