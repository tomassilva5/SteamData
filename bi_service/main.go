package main

import (
	"context"
	"log"
	"net/http"
	"time"

	"github.com/graphql-go/graphql"
	"github.com/graphql-go/handler"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	// O caminho deve coincidir com o nome definido no 'go mod init'
	pb "bi_service/proto"
)

// 1. DATA TYPES (Requisito 4: Agregação e Formatação)
// Em vez de strings puras, retornamos um objeto com metadados calculados
var gameSummaryType = graphql.NewObject(graphql.ObjectConfig{
	Name: "GameSummary",
	Fields: graphql.Fields{
		"totalResults": &graphql.Field{
			Type:        graphql.Int,
			Description: "O número de registos encontrados na base de dados para esta consulta.",
		},
		"games_xml": &graphql.Field{ // CORREÇÃO: Nome alterado para coincidir com o teu teste no Postman
			Type:        graphql.NewList(graphql.String),
			Description: "A lista de blocos XML puros recuperados via XPath/XMLTable.",
		},
	},
})

// 2. GRPC CLIENT HELPER
func getGRPCClient() (pb.SteamCatalogClient, *grpc.ClientConn, error) {
	// Ligação ao serviço Python na rede interna do Docker
	conn, err := grpc.Dial("xml_service:50051", grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, nil, err
	}
	return pb.NewSteamCatalogClient(conn), conn, nil
}

func initSchema() graphql.Schema {
	queryType := graphql.NewObject(graphql.ObjectConfig{
		Name: "Query",
		Fields: graphql.Fields{

			// QUERY 1: Filtro por Género (Atributo XPath)
			"getGamesByGenre": &graphql.Field{
				Type: gameSummaryType,
				Args: graphql.FieldConfigArgument{
					"genre": &graphql.ArgumentConfig{Type: graphql.String},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					client, conn, err := getGRPCClient()
					if err != nil { return nil, err }
					defer conn.Close()

					genre, _ := p.Args["genre"].(string)
					ctx, cancel := context.WithTimeout(context.Background(), time.Second*5)
					defer cancel()

					resp, err := client.GetGamesByFilter(ctx, &pb.GameFilterRequest{
						Filters: map[string]string{"genre": genre},
					})
					if err != nil { return nil, err }

					// AGREGAÇÃO E CÁLCULO (Requisito 4)
					return map[string]interface{}{
						"totalResults": len(resp.GamesXml),
						"games_xml":    resp.GamesXml, // CORREÇÃO: Mapeado para o novo nome
					}, nil
				},
			},

			// QUERY 2: Filtro por Ano (XPath Numérico)
			"getGamesByScore": &graphql.Field{
				Type: gameSummaryType,
				Args: graphql.FieldConfigArgument{
					"minScore": &graphql.ArgumentConfig{Type: graphql.Int},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					client, conn, err := getGRPCClient()
					if err != nil { return nil, err }
					defer conn.Close()

					minScore, _ := p.Args["minScore"].(int)
					ctx, cancel := context.WithTimeout(context.Background(), time.Second*5)
					defer cancel()

					resp, err := client.GetGamesByScore(ctx, &pb.ScoreRequest{
						MinScore: int32(minScore),
					})
					if err != nil { return nil, err }

					return map[string]interface{}{
						"totalResults": len(resp.GamesXml),
						"games_xml":    resp.GamesXml,
					}, nil
				},
			},

			// QUERY 3: Filtro por Preço Máximo (XPath Hierárquico)
			"getGamesByPrice": &graphql.Field{
				Type: gameSummaryType,
				Args: graphql.FieldConfigArgument{
					"maxPrice": &graphql.ArgumentConfig{Type: graphql.Float},
				},
				Resolve: func(p graphql.ResolveParams) (interface{}, error) {
					client, conn, err := getGRPCClient()
					if err != nil { return nil, err }
					defer conn.Close()

					maxPrice, _ := p.Args["maxPrice"].(float64)
					ctx, cancel := context.WithTimeout(context.Background(), time.Second*5)
					defer cancel()

					resp, err := client.GetGamesByPrice(ctx, &pb.PriceRequest{
						MaxUsd: float32(maxPrice),
					})
					if err != nil { return nil, err }

					return map[string]interface{}{
						"totalResults": len(resp.GamesXml),
						"games_xml":    resp.GamesXml,
					}, nil
				},
			},
		},
	})

	schema, _ := graphql.NewSchema(graphql.SchemaConfig{Query: queryType})
	return schema
}

func main() {
	schema := initSchema()
	h := handler.New(&handler.Config{
		Schema:   &schema,
		Pretty:   true,
		GraphiQL: true,
	})

	http.Handle("/graphql", h)
	log.Println("🚀 BI Service (Go) GraphQL Gateway active on http://localhost:4000/graphql")
	log.Fatal(http.ListenAndServe(":4000", nil))
}