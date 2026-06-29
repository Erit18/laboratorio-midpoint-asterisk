FROM python:3.12-alpine
WORKDIR /app
RUN apk add --no-cache docker-cli
RUN pip install --no-cache-dir flask==3.0.3
COPY app.py .
COPY templates/ templates/
COPY static/ static/
EXPOSE 5000
CMD ["python", "app.py"]
