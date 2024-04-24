FROM python:3.11-slim

WORKDIR /app

ENV TZ = Europe/Stockholm

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "./src/main.py"]