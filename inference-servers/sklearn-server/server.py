"""
Scikit-learn inference server.
Loads a .pkl/.joblib model from MODEL_PATH env var.
Exposes POST /predict with {"inputs": [[...]]} → {"predictions": [...], "latency_ms": float}
"""
import os
import time
import logging
from pathlib import Path

import joblib
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sklearn-server")

app = FastAPI(title="sklearn-inference-server", version="1.0.0")

MODEL_PATH = os.environ.get("MODEL_PATH", "")
model = None


@app.on_event("startup")
def load_model():
    global model
    if not MODEL_PATH:
        raise RuntimeError("MODEL_PATH environment variable is not set")
    path = Path(MODEL_PATH)
    if not path.exists():
        raise RuntimeError(f"Model file not found: {MODEL_PATH}")
    logger.info(f"Loading model from: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    logger.info(f"Model loaded: {type(model).__name__}")


class PredictRequest(BaseModel):
    inputs: list[list[float]]


class PredictResponse(BaseModel):
    predictions: list
    latency_ms: float
    model_type: str


@app.get("/health")
def health():
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "healthy", "model_type": type(model).__name__}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    t0 = time.perf_counter()
    try:
        X = np.array(req.inputs, dtype=np.float64)
        raw = model.predict(X)
        preds = raw.tolist()
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=422, detail=f"Prediction failed: {str(e)}")

    latency_ms = (time.perf_counter() - t0) * 1000

    return PredictResponse(
        predictions=preds,
        latency_ms=round(latency_ms, 3),
        model_type=type(model).__name__,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
