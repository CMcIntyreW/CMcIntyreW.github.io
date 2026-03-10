# Force Railway to use this instead of auto-detecting Flask dev server
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Railway sets PORT; must listen on 0.0.0.0
ENV PORT=5000
EXPOSE 5000

CMD gunicorn -w 1 -b 0.0.0.0:${PORT} app:app
