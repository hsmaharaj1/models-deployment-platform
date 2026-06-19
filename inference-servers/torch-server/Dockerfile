FROM python:3.11-slim

WORKDIR /app

# Install CPU-only PyTorch (much smaller than default CUDA build)
RUN pip install --no-cache-dir \
    torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir fastapi==0.115.5 "uvicorn[standard]==0.32.1" numpy==1.26.4 "pydantic==2.10.3"

COPY server.py .

VOLUME ["/app/artifacts"]

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
