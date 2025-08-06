from fastapi import FastAPI, Form, File, UploadFile
from typing import Annotated, List, Dict, Any
from redis.commands.search.query import Query
from fastapi.responses import HTMLResponse
from pyvis.network import Network
import networkx as nx
import os
import pickle
import numpy as np
import hashlib
import redis
import vec
import db
import shutil

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

r = redis.Redis(host="localhost", port=6379)

db.create_index(r, 512)

GRAPH_FILE = "semantic_graph.pkl"
if os.path.exists(GRAPH_FILE):
    with open(GRAPH_FILE, "rb") as f:
        semantic_graph = pickle.load(f)
else:
    semantic_graph = nx.Graph()

def save_graph():
    with open(GRAPH_FILE, "wb") as f:
        pickle.dump(semantic_graph, f)

@app.get("/")
async def read_root():
    return {"message": "Hello, Redis!"}

@app.post("/submit")
async def submit_task(
    mtype: Annotated[str, Form(alias="type")],
    data: Annotated[str, Form(alias="data")] = None,
    file: UploadFile = File(None, alias="file")
):
    print(f"Received submission type: {mtype}")

    if mtype == "text":
        content = data
    elif mtype in ("image", "audio"):
        if not file:
            return {"error": "No file uploaded."}
        file_bytes = await file.read()
        hash_val = generate_hash(file_bytes)
        filename = f"{hash_val}{os.path.splitext(file.filename)[1]}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        content = file_path
    else:
        return {"error": "Unsupported type. Use 'text', 'image', or 'audio'."}

    v = vec.toVect({"type": mtype, "data": content})
    print("Length of vector:", len(v))
    if v is None:
        return {"error": "Failed to create vector."}

    key = f"doc:{generate_hash(content if mtype == 'text' else file_bytes)}"

    if not r.exists(key):
        db.storeVec(key, v, content if mtype == "text" else filename, r, mtype)

    result = search_knn(r, v, 5)
    update_graph_connections(semantic_graph, key, result)

    return {"message": f"Stored {mtype}", "key": key, "neighbors": result}


@app.post("/search")
async def search_knn_endpoint(
    mtype: Annotated[str, Form(alias="type")],
    data: Annotated[str, Form(alias="data")] = None,
    file: UploadFile = File(None, alias="file")
):
    print(f"Graph search type: {mtype}")
    top_k = 5

    if mtype == "text":
        query_content = data
        hash_val = generate_hash(query_content)
    elif mtype in ("image", "audio"):
        if not file:
            return {"error": "No file uploaded."}
        file_bytes = await file.read()
        hash_val = generate_hash(file_bytes)
        filename = f"{hash_val}{os.path.splitext(file.filename)[1]}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        query_content = file_path
    else:
        return {"error": "Unsupported type. Use 'text', 'image', or 'audio'."}

    key = f"doc:{hash_val}"

    if key in semantic_graph:
        neighbors = []
        for neighbor in semantic_graph.neighbors(key):
            score = semantic_graph[key][neighbor].get("score", 0)
            neighbor_data = r.hget(neighbor, "data")
            neighbor_type = r.hget(neighbor, "type")
            neighbors.append({
                "id": neighbor,
                "score": score,
                "data": neighbor_data.decode() if neighbor_data else None,
                "type": neighbor_type.decode() if neighbor_type else None
            })
        neighbors.sort(key=lambda x: x["score"], reverse=True)
        return {"results": neighbors[:top_k]}

    query_vec = vec.toVect({"type": mtype, "data": query_content})
    if query_vec is None:
        return {"error": "Failed to create query vector."}

    search_results = search_knn(r, query_vec, top_k)

    db.storeVec(key, query_vec, query_content if mtype == "text" else filename, r, mtype)
    update_graph_connections(
        semantic_graph,
        key,
        [{"id": item["id"], "score": item["score"]} for item in search_results]
    )

    return {"results": search_results}


@app.get("/graph")
async def get_graph():
    net = Network(
        height="100%",
        width="100%",
        bgcolor="#121212",
        font_color="white"
    )

    net.barnes_hut(gravity=-2000, spring_length=200, spring_strength=0.02)

    type_colors = {
        "text": "#4db6ff",
        "image": "#76ff7a",
        "audio": "#ff9800"
    }

    for node in semantic_graph.nodes:
        node_data = r.hget(node, "data")
        node_type = r.hget(node, "type")

        label = node_data.decode() if node_data else node
        ntype = node_type.decode() if node_type else "unknown"

        net.add_node(
            node,
            label=label,
            color=type_colors.get(ntype, "#9e9e9e"),
            shape="dot",
            size=25,
            font={"size": 14},
            title=f"Type: {ntype}"
        )

    for u, v, data in semantic_graph.edges(data=True):
        score = data.get("score", 0)
        net.add_edge(
            u, v,
            title=f"Score: {score:.4f}",
            color="rgba(255,255,255,0.4)",
            smooth={"type": "dynamic"}
        )

    html_content = net.generate_html(notebook=False)
    full_screen_css = """
    <style>
        html, body {
            margin: 0;
            padding: 0;
            height: 100%;
            overflow: hidden;
            background-color: #121212;
        }
        #mynetwork {
            width: 100%;
            height: 100vh !important;
        }
    </style>
    """
    html_content = html_content.replace("</head>", full_screen_css + "</head>")

    return HTMLResponse(content=html_content)

def search_knn(r, query_vector, k=5):
    query_vector_bytes = vector_to_bytes(query_vector)
    q = (
        Query(f"*=>[KNN {k} @embedding $vector AS vector_score]")
        .sort_by("vector_score")
        .return_fields("id", "data", "type", "vector_score")
        .dialect(2)
    )
    params = {"vector": query_vector_bytes}
    results = r.ft("idx:docs").search(q, query_params=params)
    
    parsed_results = []
    for doc in results.docs:
        similarity = 1 - float(doc.vector_score)
        parsed_results.append({
            "id": doc.id,
            "data": doc.data,
            "type": doc.type,
            "score": similarity
        })
    return parsed_results

def update_graph_connections(graph: nx.Graph, source_key: str, neighbors: list[dict]):
    graph.add_node(source_key)
    for n in neighbors:
        target_id = n["id"]
        if target_id == source_key:
            continue
        graph.add_node(target_id)
        graph.add_edge(source_key, target_id, score=n["score"])
    save_graph()
    print(f"✅ Graph updated: {source_key} connected to {len(neighbors)} neighbors (self skipped).")

def generate_hash(data) -> str:
    if isinstance(data, str):
        encoded_data = data.encode('utf-8')
    else:
        encoded_data = data  # bytes
    return hashlib.sha256(encoded_data).hexdigest()

def vector_to_bytes(vector: List[float]) -> bytes:
    return np.array(vector, dtype=np.float32).tobytes()
