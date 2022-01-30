FROM python:slim

RUN mkdir -p /code
RUN mkdir -p /data
WORKDIR /code
COPY ./pip-requirements.txt /code/pip-requirements.txt

RUN pip install --upgrade pip
RUN pip install -r pip-requirements.txt

COPY ./code /code

ENV FLASK_APP=main
ENV FLASK_DEBUG=1
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
