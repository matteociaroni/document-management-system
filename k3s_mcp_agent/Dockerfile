FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 8000 for webhook, 8001 for MCP server (if accessed externally)
EXPOSE 8000 8001

CMD ["python", "main.py"]
