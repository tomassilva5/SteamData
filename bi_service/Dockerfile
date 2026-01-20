# 1. Usar a versão estável mais recente
FROM golang:1.24-alpine

# 2. Instalar dependências e protoc
RUN apk add --no-cache protobuf protobuf-dev git

# 3. Plugins gRPC para Go
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

WORKDIR /app

# 4. Copiar e baixar dependências iniciais
COPY go.mod go.sum ./
RUN go mod download

# 5. Copiar o resto do código
COPY . .

# 6. GERAR gRPC e SINCRONIZAR dependências (Importante!)
RUN protoc --proto_path=. --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    proto/steam.proto

# Executa o tidy para registar as dependências do gRPC gerado
RUN go mod tidy

# 7. Build do executável
RUN go build -o bi_service main.go

EXPOSE 4000
CMD ["./bi_service"]