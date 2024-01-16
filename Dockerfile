FROM python:3.8-slim

RUN apt-get update && apt-get -y install cron

WORKDIR /usr/src/app

# The requirements need some work
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ADD crontab /etc/cron.d/my-cron-file

RUN chmod 0644 /etc/cron.d/my-cron-file

RUN crontab /etc/cron.d/my-cron-file

RUN touch /var/log/cron.log

RUN cron && tail -f /var/log/cron.log