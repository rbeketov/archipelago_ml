FROM python:3.9

WORKDIR /app
COPY init_script.py /app/init_script.py
RUN pip install qdrant-client

CMD ["python", "/app/init_script.py"]
