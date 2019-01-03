FROM python:3.6-slim-stretch

COPY . /
RUN pip install -r requirements.txt

EXPOSE 5000
CMD flask run -h 0.0.0.0 -p $PORT