# Force Railway to use this instead of auto-detecting Flask dev server
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Railway sets PORT; start.sh ensures it expands at runtime
ENV PORT=5000
EXPOSE 5000

RUN chmod +x start.sh
CMD ["./start.sh"]
