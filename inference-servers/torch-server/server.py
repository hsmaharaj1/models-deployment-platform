"""
PyTorch inference server.
Loads a .pt/.pth model from MODEL_PATH env var.
Supports:
  - torch.nn.Module (loaded via torch.load with weights_only=False, wrapped in eval())
  - TorchScript models (torch.jit.load)
Exposes POST /predict with {"inputs": [[...]]} → {"predictions": [...], "latency_ms": float}
"""
import os
import time
import logging
from pathlib import Path

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("torch-server")

app = FastAPI(title="torch-inference-server", version="1.0.0")

MODEL_PATH = os.environ.get("MODEL_PATH", "")
model = None
model_type_name = "unknown"


@app.on_event("startup")
def load_model():
    global model, model_type_name
    if not MODEL_PATH:
        raise RuntimeError("MODEL_PATH environment variable is not set")
    path = Path(MODEL_PATH)
    if not path.exists():
        raise RuntimeError(f"Model file not found: {MODEL_PATH}")

    logger.info(f"Loading torch model from: {MODEL_PATH}")

    # Try TorchScript first (safer), then full load
    try:
        model = torch.jit.load(MODEL_PATH, map_location="cpu")
        model_type_name = "TorchScript"
        logger.info("Loaded as TorchScript model")
    except Exception:
        model = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
        model_type_name = type(model).__name__
        logger.info(f"Loaded as {model_type_name}")

    if hasattr(model, "eval"):
        model.eval()
    logger.info(f"Model ready: {model_type_name}")


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
    return {"status": "healthy", "model_type": model_type_name}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    t0 = time.perf_counter()
    try:
        X = torch.tensor(req.inputs, dtype=torch.float32)
        with torch.no_grad():
            output = model(X)
        # Convert to Python list
        if isinstance(output, torch.Tensor):
            preds = output.tolist()
        else:
            preds = list(output)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=422, detail=f"Prediction failed: {str(e)}")

    latency_ms = (time.perf_counter() - t0) * 1000

    return PredictResponse(
        predictions=preds,
        latency_ms=round(latency_ms, 3),
        model_type=model_type_name,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
