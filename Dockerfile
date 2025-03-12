FROM python:3.13.2-bookworm

WORKDIR /app

COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "app.py"]
