package main

import (
	"context"
	"fmt"
	"log"
	"rediscontest/database"
	"rediscontest/utils"
	"strconv"
	"strings"

	"github.com/RedisGraph/redisgraph-go"
	rg "github.com/RedisGraph/redisgraph-go"
	"github.com/gomodule/redigo/redis"
	rv "github.com/redis/go-redis/v9"

	"github.com/gin-gonic/gin"
)

var (
	client *redis.Conn
	gored  *rv.Client
	graph  redisgraph.Graph
	ctx    = context.Background()
)

func main() {
	r := gin.Default()

	client, _ := redis.Dial("tcp", "127.0.0.1:6379", redis.DialPassword("pass"))
	graph = redisgraph.GraphNew("semantic_graph", client)

	gored = rv.NewClient(&rv.Options{
		Addr:     "localhost:6379",
		Password: "pass",
	})

	vectorDimension := 512

	if err := createVectorIndex(gored, vectorDimension); err != nil {
		log.Fatalf("Failed to create vector index: %v", err)
	}

	fmt.Println("Vector index created or already exists.")

	r.POST("/search", searchHandler)
	r.POST("/submit", submitHandler)

	r.Run(":8080")
}

type Input struct {
	Text string `json:"text"`
}

func submitHandler(c *gin.Context) {
	searchType, ok := c.GetPostForm("type")
	if !ok {
		log.Println("Search type not provided")
		c.JSON(400, gin.H{"error": "Search type is required"})
		return
	}

	ctx := context.Background()
	rdb := client

	switch searchType {
	case "text":
		var input Input
		if err := c.ShouldBindJSON(&input); err != nil {
			log.Println("Error binding JSON:", err)
			c.JSON(400, gin.H{"error": "Invalid input"})
			return
		}

		queryText := strings.TrimSpace(strings.ToLower(input.Text))
		fmt.Println("Search query:", queryText)

		vec, err := utils.ToVector(input.Text, "text")
		if err != nil {
			log.Printf("Embedding error: %v\n", err)
			c.JSON(500, gin.H{"error": "Failed to generate vector embedding"})
			return
		}
		fmt.Printf("Vector for text: %v\n", vec)

		hashKey := "doc:text:" + utils.Sha256Sum(queryText)

		exists, err := KeyExists(client, hashKey)
		if err != nil {
			log.Printf("Redis Exists error: %v\n", err)
			c.JSON(500, gin.H{"error": "Failed to check existing key"})
			return
		}

		if exists == true {
			// If node exists, maybe increment usage count or update timestamp here
			log.Println("Document already exists, skipping storage")
		} else {
			err = database.StoreVector(gored, vec, ctx, hashKey, queryText)
			if err != nil {
				log.Printf("StoreVector error: %v\n", err)
				c.JSON(500, gin.H{"error": "Failed to store vector"})
				return
			}
			log.Printf("Stored new document with key: %s\n", hashKey)
		}

		// Perform KNN search to find similar documents
		k := 5 // number of neighbors
		similarKeys, similarities, err := searchSimilarVectorsWithScores(gored, vec, k)
		if err != nil {
			log.Printf("KNN search error: %v\n", err)
			c.JSON(500, gin.H{"error": "KNN search failed"})
			return
		}
		log.Printf("Similar keys found: %v\n", similarKeys)

		// Upsert query node and edges into RedisGraph
		graph := rg.GraphNew("semantic_graph", (*rdb))
		err = connectToGraph(&graph, hashKey, similarKeys, similarities)
		if err != nil {
			log.Printf("Graph update error: %v\n", err)
			c.JSON(500, gin.H{"error": "Failed to update graph"})
			return
		}

		// Return success with possible data
		c.JSON(200, gin.H{"status": "success", "similar_keys": similarKeys})

	case "file":
		fileHeader, err := c.FormFile("file")
		if err != nil {
			log.Printf("File upload error: %v\n", err)
			c.JSON(400, gin.H{"error": "File not provided or invalid"})
			return
		}
		log.Printf("Received file: %s\n", fileHeader.Filename)
	}
}

func searchHandler(c *gin.Context) {
	Searchtype, bool := c.GetPostForm("type")
	if !bool {
		log.Println("Search type not provided")
		c.JSON(400, gin.H{"error": "Search type is required"})
		return
	}

	switch Searchtype {
	case "text":
		query, _ := c.GetPostForm("query")
		fmt.Println("Search query:", query)

	case "file":
		query, _ := c.FormFile("file")
		fmt.Println("Search query:", query)
	}
}

func createVectorIndex(rdb *rv.Client, dim int) error {
	ctx := context.Background()
	res := rdb.Do(ctx,
		"FT.CREATE", "idx:text:vector",
		"ON", "HASH",
		"PREFIX", "1", "doc:",
		"SCHEMA",
		"type", "TAG",
		"content", "TEXT",
		"embedding", "VECTOR", "HNSW", "6",
		"DIM", fmt.Sprint(dim),
		"DISTANCE_METRIC", "COSINE",
		"INITIAL_CAP", "1000",
		"M", "16",
		"EF_CONSTRUCTION", "200",
	)
	if res.Err() != nil && !strings.Contains(res.Err().Error(), "Index already exists") {
		return res.Err()
	}
	return nil
}

func searchSimilarVectorsWithScores(rdb *rv.Client, queryVec []float32, k int) ([]string, []float64, error) {
	ctx := context.Background()
	vecBytes := utils.Float32SliceToBytes(queryVec)
	query := fmt.Sprintf("*=>[KNN %d @embedding $query_vec AS vector_score]", k)
	res, err := rdb.Do(ctx,
		"FT.SEARCH", "idx:text:vector", query,
		"PARAMS", "2", "query_vec", vecBytes,
		"SORTBY", "vector_score",
		"RETURN", "2", "content", "vector_score",
		"DIALECT", "2",
	).Result()
	if err != nil {
		return nil, nil, err
	}

	arr, ok := res.([]interface{})
	if !ok || len(arr) < 2 {
		return nil, nil, fmt.Errorf("unexpected result format: %v", res)
	}

	keys := []string{}
	scores := []float64{}
	// arr[0] is the total count
	for i := 1; i < len(arr); i += 2 {
		key, _ := arr[i].(string)
		keys = append(keys, key)
		// Next element: fields array
		fields, _ := arr[i+1].([]interface{})
		// Parse vector_score field
		var score float64
		for j := 0; j < len(fields); j += 2 {
			fname, _ := fields[j].(string)
			if fname == "vector_score" || fname == "VECTOR_SCORE" {
				sval, _ := fields[j+1].(string)
				f, err := strconv.ParseFloat(sval, 64)
				if err == nil {
					score = f
				}
			}
		}
		scores = append(scores, score)
	}
	return keys, scores, nil
}

func connectToGraph(rgClient *rg.Graph, queryKey string, similarKeys []string, similarities []float64) error {
	// Assumes queryKey and similarKeys are doc keys (e.g., "doc:text:abcd1234...")
	// similarities is of length len(similarKeys) (produced by parsing vector_score field)
	// 1. Create the query node if not exist
	// 2. Create edges of type "SIMILAR" from query to each similar node with weight=similarity

	query := ""

	// Cypher upsert for the query node (id is unique)
	query += fmt.Sprintf("MERGE (q:Text {id: '%s'})\n", queryKey)
	for i, skey := range similarKeys {
		sim := similarities[i]
		rel := fmt.Sprintf(
			"MERGE (n%d:Text {id: '%s'})\nMERGE (q)-[:SIMILAR {weight: %f}]->(n%d)\n",
			i, skey, sim, i)
		query += rel
	}

	_, err := rgClient.Query(query)
	return err
}

func KeyExists(conn *redis.Conn, key string) (bool, error) {
	return redis.Bool((*conn).Do("EXISTS", key))
}
