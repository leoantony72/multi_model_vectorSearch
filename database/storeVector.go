package database

import (
	"context"

	"github.com/redis/go-redis/v9"
)

func StoreVector(db *redis.Client, vector []float32, ctx context.Context, key string, data string) error {
	db.HSet(ctx, key, "vector", vector, "type", "text", "data", data)

	err := db.HSet(ctx, key, map[string]interface{}{
		"embedding": vector,
		"type":      "text",
		"content":   data,
	}).Err()
	if err != nil {
		return err
	}
	return nil
}
