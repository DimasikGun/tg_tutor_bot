FROM python:3.10.13-alpine
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt
WORKDIR /app
COPY bot /app/bot
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
CMD ["sh", "-c", "sleep 10 && alembic upgrade head && python -m bot"]
