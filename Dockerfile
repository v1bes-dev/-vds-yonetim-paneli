FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ajan_whatsapp.py db.py pii.py audit.py guardrails.py grounding.py rate_limit.py .

CMD ["python", "-u", "ajan_whatsapp.py"]
