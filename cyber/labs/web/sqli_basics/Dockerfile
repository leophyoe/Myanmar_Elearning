FROM python:3.12-alpine

WORKDIR /app

RUN pip install --no-cache-dir flask

COPY app.py /app/app.py

EXPOSE 5000

ENV FLASK_APP=app.py

CMD ["python", "app.py"]

