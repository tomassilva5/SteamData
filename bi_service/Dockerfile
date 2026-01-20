FROM golang:1.24-alpine

RUN apk add --no-cache protobuf protobuf-dev git

RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
RUN go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

WORKDIR /app

COPY go.mod go.sum ./
RUN go mod download

COPY . .

RUN protoc --proto_path=. --go_out=. --go_opt=paths=source_relative \
    --go-grpc_out=. --go-grpc_opt=paths=source_relative \
    proto/steam.proto

RUN go mod tidy

RUN go build -o bi_service main.go

EXPOSE 4000
CMD ["./bi_service"]