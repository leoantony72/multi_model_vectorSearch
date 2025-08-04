package database

import (
	"bytes"
	"context"
	"encoding/binary"
	"fmt"

	"github.com/redis/go-redis/v9"
)

func StoreVector(db *redis.Client, vector []float32, ctx context.Context, key string, data string) error {
	buf := new(bytes.Buffer)
	for _, f := range vector {
		err := binary.Write(buf, binary.LittleEndian, f)
		if err != nil {
			return fmt.Errorf("failed to write float to buffer: %w", err)
		}
	}

	vectorBytes := buf.Bytes()
	err := db.HSet(ctx, key, map[string]interface{}{
		"embedding": vectorBytes,
		"type":      "text",
		"content":   data,
	}).Err()
	if err != nil {
		return fmt.Errorf("StoreVector error: %w", err)
	}

	return nil
}
