FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# Model artifacts are mounted at /app/artifacts
VOLUME ["/app/artifacts"]

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
