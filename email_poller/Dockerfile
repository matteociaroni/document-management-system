FROM python:3.14-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY email-poller/ .


# Run uvicorn
CMD ["python", "poller.py"]
