FROM python:3.12-slim

# Dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Zona horaria (ajusta a la tuya)
ENV TZ=Europe/Madrid
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Instalar Poetry
ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv
ENV POETRY_CACHE_DIR=/opt/.cache

RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install --upgrade pip \
    && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION}

ENV PATH="${POETRY_VENV}/bin:${PATH}"

WORKDIR /app

# Copiar archivos de dependencias primero (mejor cache de Docker)
COPY pyproject.toml poetry.lock* ./

# Instalar dependencias sin crear virtualenv (ya estamos en contenedor)
# Si no hay poetry.lock lo genera automáticamente antes de instalar
RUN poetry config virtualenvs.create false \
    && ([ -f poetry.lock ] || poetry lock) \
    && poetry install --only main --no-interaction --no-ansi --no-root

# Copiar código fuente
COPY main.py ./
COPY garmin_coach/ ./garmin_coach/

# Volumen para datos persistentes
VOLUME ["/data"]

RUN mkdir -p /data/logs && rm -rf ./garmin_coach/tests

CMD ["/usr/local/bin/python", "main.py"]
