package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"rediscontest/database"
	"rediscontest/utils"
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
		data := c.PostForm("query")
		queryText := strings.TrimSpace(strings.ToLower(data))
		fmt.Println("Search query:", queryText)

		vec, err := utils.ToVector(data, "text")
		if err != nil {
			log.Printf("Embedding error: %v\n", err)
			c.JSON(500, gin.H{"error": "Failed to generate vector embedding"})
			return
		}
		fmt.Printf("Vector for text: %v\n", vec)

		hashKey := "doc:text:" + utils.Sha256Sum(queryText)

		exists, err := KeyExists(gored, ctx, hashKey)
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
		similarKeys, _, similarities, err := searchSimilarVectorsWithScores(gored, vec, k)
		if err != nil {
			log.Printf("KNN search error: %v\n", err)
			c.JSON(500, gin.H{"error": "KNN search failed"})
			return
		}
		log.Printf("Similar keys found: %v\n", similarKeys)

		// Insert query node and edges into RedisGraph
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
	hnswArgs := []string{
		"HNSW", "12",
		"TYPE", "FLOAT32",
		"DIM", fmt.Sprint(dim),
		"DISTANCE_METRIC", "COSINE",
		"INITIAL_CAP", "1000",
		"M", "16",
		"EF_CONSTRUCTION", "200",
	}

	stringArgs := []string{
		"FT.CREATE", "idx:text:vector",
		"ON", "HASH",
		"PREFIX", "1", "doc:",
		"SCHEMA",
		"type", "TAG",
		"content", "TEXT",
		"embedding", "VECTOR",
	}
	stringArgs = append(stringArgs, hnswArgs...)
	iargs := make([]interface{}, len(stringArgs))
	for i, v := range stringArgs {
		iargs[i] = v
	}

	res := rdb.Do(ctx, iargs...)
	if res.Err() != nil && !strings.Contains(res.Err().Error(), "Index already exists") {
		return res.Err()
	}

	fmt.Println("Vector index created or already exists.")
	return nil
}

func searchSimilarVectorsWithScores(rdb *rv.Client, queryVec []float32, k int) ([]string, []string, []float64, error) {
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
		return nil, nil, nil, fmt.Errorf("KNN search command failed: %w", err)
	}

	resultMap, ok := res.(map[string]interface{})
	if !ok {
		return nil, nil, nil, fmt.Errorf("unexpected result format: expected map, got %T", res)
	}

	results, ok := resultMap["results"].([]interface{})
	if !ok {
		return nil, nil, nil, fmt.Errorf("results field is not a slice")
	}

	// 1. Declare slices for all return values.
	var keys []string
	var contents []string
	var scores []float64

	for _, resultItem := range results {
		doc, ok := resultItem.(map[string]interface{})
		if !ok {
			continue
		}

		// 2. Extract the document ID.
		if id, found := doc["id"].(string); found {
			keys = append(keys, id)
		}

		attributes, ok := doc["extra_attributes"].(map[string]interface{})
		if !ok {
			continue
		}

		if content, found := attributes["content"].(string); found {
			contents = append(contents, content)
		}
		if score, found := attributes["vector_score"].(float64); found {
			scores = append(scores, score)
		}
	}

	// 3. Return all four values in the correct order.
	return keys, contents, scores, nil
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

func KeyExists(rdb *rv.Client, ctx context.Context, key string) (bool, error) {
	if rdb == nil {
		return false, errors.New("redis client is nil")
	}
	count, err := rdb.Exists(ctx, key).Result()
	if err != nil {
		return false, err
	}
	return count > 0, nil
}
