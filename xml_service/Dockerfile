FROM python:3.10

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev gcc python3-dev musl-dev

COPY src /app/src
COPY proto /app/proto

RUN pip install --no-cache-dir grpcio grpcio-tools lxml psycopg2-binary flask requests supabase

RUN python -m grpc_tools.protoc -I/app/proto --python_out=/app/proto --grpc_python_out=/app/proto /app/proto/steam.proto

EXPOSE 50051
EXPOSE 5000

CMD ["python3", "-u", "src/xml_service.py"]