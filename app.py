from flask import Flask, request, jsonify
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import torch
import torch.nn.functional as F
import io
import base64

app = Flask(__name__)
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch16")
clip_proc = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch16")
clip_model.eval()

def normalize_embedding(tensor):
    return F.normalize(tensor, p=2, dim=-1)

@app.route("/embed", methods=["POST"])
def embed():
    data = request.get_json()
    result = []

    if 'text' in data:
        text_emb = clip_model.get_text_features(
            **clip_proc(text=[data['text']], return_tensors="pt")
        )
        text_emb = normalize_embedding(text_emb)  # ✅ Normalize
        text_emb = text_emb[0].detach().cpu().numpy().astype('float32').tolist()
        print(f"[INFO] Text embedding dimension: {len(text_emb)} (normalized)")
        result.append(text_emb)

    elif 'image' in data:
        image_data = base64.b64decode(data['image'])
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        img_emb = clip_model.get_image_features(
            **clip_proc(images=image, return_tensors="pt")
        )
        img_emb = normalize_embedding(img_emb)  # ✅ Normalize
        img_emb = img_emb[0].detach().cpu().numpy().astype('float32').tolist()
        print(f"[INFO] Image embedding dimension: {len(img_emb)} (normalized)")
        result.append(img_emb)

    else:
        return jsonify({"error": "Specify 'text' or 'image'."}), 400

    return jsonify(result)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8009)
