package main

import (
	"fmt"
	"log"
	"rediscontest/database"
	"rediscontest/utils"

	"github.com/redis/go-redis/v9"

	"github.com/gin-gonic/gin"
)

var client *redis.Client

func main() {
	r := gin.Default()

	client = redis.NewClient(&redis.Options{
		Addr:     "localhost:6379",
		Password: "pass",
	})

	r.POST("/search", searchHandler)
	r.POST("/submit", submitHandler)

	r.Run(":8080")
}

func submitHandler(c *gin.Context) {
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
		vec, err := utils.ToVector("hello world", "text")
		fmt.Printf("Vector for text: %v, error: %v\n", vec, err)

		database.StoreVector(client, vec, "text_query")

	case "file":
		query, _ := c.FormFile("file")
		fmt.Println("Search file:", query.Filename)
	}

	c.JSON(200, gin.H{"status": "success"})
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
