FROM python:3.10-buster

EXPOSE 8086

COPY ./requirements.txt /app/requirements.txt

RUN pip install -r /app/requirements.txt

RUN apt-get update
RUN apt-get -y install apt-transport-https ca-certificates curl gnupg2 software-properties-common

COPY . /app

WORKDIR /app/src/main/python

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8086", "--log-level", "debug" ]
