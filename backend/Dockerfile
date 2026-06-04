FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 顔認識を有効化する場合 true（InsightFace/OpenCVの追加ランタイムも導入）
ARG INSTALL_FACE=false

WORKDIR /app

COPY requirements.txt requirements-face.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$INSTALL_FACE" = "true" ]; then \
        apt-get update && \
        apt-get install -y --no-install-recommends \
            build-essential python3-dev libglib2.0-0 libgl1 && \
        pip install --no-cache-dir -r requirements-face.txt && \
        apt-get purge -y build-essential python3-dev && \
        apt-get autoremove -y && \
        rm -rf /var/lib/apt/lists/*; \
    fi

COPY . .
RUN chmod +x entrypoint.sh

EXPOSE 8017

CMD ["./entrypoint.sh"]
