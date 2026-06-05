FROM coady/pylucene:9.12.0

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 5000

ENV FLASK_APP=hello.py \
    FLASK_DEBUG=1 \
    PYTHONUNBUFFERED=1

CMD ["python", "hello.py"]