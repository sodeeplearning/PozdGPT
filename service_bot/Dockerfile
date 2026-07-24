FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY ./service_bot/requirements.txt .

RUN pip install --upgrade pip \
 && pip install -r requirements.txt

COPY ./service_bot .
COPY config.py config.py
COPY .env .env
COPY ./docs ./docs

CMD ["python", "main.py"]
