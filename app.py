from flask import Flask, request, jsonify
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import torch
import io
import base64

app = Flask(__name__)
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
clip_proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")

@app.route("/embed", methods=["POST"])
def embed():
    data = request.get_json()
    result = []

    if 'text' in data:
        text_emb = clip_model.get_text_features(
            **clip_proc(text=[data['text']], return_tensors="pt")
        )[0].detach().cpu().numpy().tolist()
        print(f"[INFO] Text embedding dimension: {len(text_emb)}")
        result.append(text_emb)

    elif 'image' in data:
        # Accepts image as base64 string
        image_data = base64.b64decode(data['image'])
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        img_emb = clip_model.get_image_features(
            **clip_proc(images=image, return_tensors="pt")
        )[0].detach().cpu().numpy().tolist()
        print(f"[INFO] Image embedding dimension: {len(img_emb)}")
        result.append(img_emb)

    else:
        return jsonify({"error": "Specify 'text' or 'image'."}), 400

    return jsonify(result)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8009)
