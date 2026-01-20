FROM python:3.10

WORKDIR /app

# 1. Instalar dependências do sistema necessárias para o psycopg2 e lxml
RUN apt-get update && apt-get install -y libpq-dev gcc python3-dev musl-dev

# 2. Copiar apenas o que existe na pasta xml_service
COPY src /app/src
COPY proto /app/proto

# 3. Instalar bibliotecas Python (Removido pandas se não usares, para ser mais rápido)
RUN pip install --no-cache-dir grpcio grpcio-tools lxml psycopg2-binary flask requests supabase

# 4. Gerar os ficheiros gRPC a partir do .proto
# Nota: O caminho no contentor é /app/proto
RUN python -m grpc_tools.protoc -I/app/proto --python_out=/app/proto --grpc_python_out=/app/proto /app/proto/steam.proto

EXPOSE 50051
EXPOSE 5000

# Usar a flag -u para garantir que os logs aparecem no Docker em tempo real
CMD ["python3", "-u", "src/xml_service.py"]