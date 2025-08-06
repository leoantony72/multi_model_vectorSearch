import requests
import json

url = "http://localhost:8009/embed"
import requests
import base64

def toVect(payload):
    try:
        # Prepare payload for the embedding API
        api_payload = {}

        if payload.get("type") == "text":
            api_payload["text"] = payload["data"]

        elif payload.get("type") in ("image", "audio"):
            file_path = payload["data"]
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            api_payload["image"] = base64.b64encode(file_bytes).decode("utf-8") \
                if payload["type"] == "image" else base64.b64encode(file_bytes).decode("utf-8")
            # If you later add audio embedding, adjust here for audio API

        else:
            print(f"Unsupported type in toVect: {payload.get('type')}")
            return None

        # Send request to embedding API
        response = requests.post(url, json=api_payload)
        response.raise_for_status()

        data = response.json()

        if isinstance(data, list) and data:
            vector = data[0]
            print(f"Vector received successfully. Dimension: {len(vector)}")
            return vector
        else:
            print(f"Error: Unexpected response format: {data}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None
