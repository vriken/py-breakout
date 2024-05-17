FROM python:3.11-slim

WORKDIR /app

ENV TZ=Europe/Stockholm

# Copy only the necessary files
COPY ./requirements.txt ./requirements.txt
COPY ./src/*.py ./src/
COPY ./input/ ./input/

RUN pip install pipreqs
RUN pipreqs --force

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "./src/main.py"]
