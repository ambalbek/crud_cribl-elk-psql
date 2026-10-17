FROM python:3.12

WORKDIR /app

RUN pip install --no-cache-dir \
    requests==2.34.2 \
    azure-storage-blob==12.30.2 \
    azure-identity==1.25.3

COPY get_apmids_from_blob.py .

ENTRYPOINT ["python", "get_apmids_from_blob.py"]
