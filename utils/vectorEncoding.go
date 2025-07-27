package utils

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	// "github.com/redis/go-redis/v9"
)

func ToVector(data interface{}, dataType string) ([]float32, error) {
	apiURL := "http://127.0.0.1:8009/embed"
	client := &http.Client{}

	var req *http.Request
	var err error

	switch dataType {
	case "text":
		text, ok := data.(string)
		if !ok {
			return nil, errors.New("for 'text' dataType, data must be a string")
		}
		jsonBody, err := json.Marshal(map[string]string{"text": text})
		if err != nil {
			return nil, err
		}
		req, err = http.NewRequestWithContext(context.Background(), "POST", apiURL, bytes.NewBuffer(jsonBody))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Content-Type", "application/json")

	case "image":
		b, ok := data.([]byte)
		if !ok {
			return nil, errors.New("for 'image' dataType, data must be []byte")
		}
		encoded := base64.StdEncoding.EncodeToString(b)
		jsonBody, err := json.Marshal(map[string]string{"image": encoded})
		if err != nil {
			return nil, err
		}
		req, err = http.NewRequestWithContext(context.Background(), "POST", apiURL, bytes.NewBuffer(jsonBody))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Content-Type", "application/json")

	default:
		return nil, fmt.Errorf("unsupported dataType: %s", dataType)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("non-OK HTTP status: %d, body: %s", resp.StatusCode, string(bodyBytes))
	}

	respBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	// Parse as [][]float64, fallback []float64
	var nested [][]float64
	if err := json.Unmarshal(respBytes, &nested); err != nil {
		var flat []float64
		if err2 := json.Unmarshal(respBytes, &flat); err2 != nil {
			return nil, fmt.Errorf("failed to parse embedding json: %v, fallback error: %v", err, err2)
		}
		nested = [][]float64{flat}
	}
	if len(nested) == 0 || len(nested[0]) == 0 {
		return nil, fmt.Errorf("empty embedding returned: %s", string(respBytes))
	}

	embedding := make([]float32, len(nested[0]))
	for i, v := range nested[0] {
		embedding[i] = float32(v)
	}
	return embedding, nil
}
