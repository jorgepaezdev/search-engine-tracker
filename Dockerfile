FROM python:3.10-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 48621

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "48621"]
