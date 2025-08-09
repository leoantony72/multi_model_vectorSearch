from fastapi import FastAPI, Form, File, UploadFile
from typing import Annotated, List
from redis.commands.search.query import Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pyvis.network import Network
from fastapi.staticfiles import StaticFiles
import networkx as nx
import os
import pickle
import numpy as np
import hashlib
import redis
import vec
import db
import search

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

r = redis.Redis(host="localhost", port=6379)

# Create Redis index
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


app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
async def read_root():
    return FileResponse('index.html', media_type='text/html')


@app.post("/submit")
async def submit_task(
    mtype: Annotated[str, Form(alias="type")],
    data: Annotated[str, Form(alias="data")] = None,
    file: UploadFile = File(None, alias="file")
):
    print(f"Received submission type: {mtype}")

    # Handle text or file uploads
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

    # Get embedding vector
    v = vec.toVect({"type": mtype, "data": content})
    if v is None:
        return {"error": "Failed to create vector."}
    print("Length of vector:", len(v))

    key = f"doc:{generate_hash(content if mtype == 'text' else file_bytes)}"

    if not r.exists(key):
        db.storeVec(key, v, content if mtype == "text" else filename, r, mtype)

    # Search neighbors with improved logic
    result = search_knn(r, v, 5, query_id=key, query_type=mtype)
    update_graph_connections(semantic_graph, key, result)

    return {"message": f"Stored {mtype}", "key": key, "neighbors": result}


@app.post("/search")
async def search_endpoint_with_graph(
    mtype: Annotated[str, Form(alias="type")],
    query: Annotated[str, Form(alias="query")] = None,
    file: UploadFile = File(None, alias="file")
):
    print(f"Graph-augmented search: type={mtype}")
    top_k = 12
    if mtype == "text":
        if not query:
            return {"error": "Text query required for type='text'"}
        query_vec = vec.toVect({"type": "text", "data": query})
    elif mtype in ("image", "audio"):
        if not file:
            return {"error": f"File required for type='{mtype}'"}
        file_bytes = await file.read()
        temp_filename = f"temp_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, temp_filename)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        query_vec = vec.toVect({"type": mtype, "data": file_path})
        os.remove(file_path)
    else:
        return {"error": "Unsupported type. Use 'text', 'image', or 'audio'."}

    if query_vec is None:
        return {"error": "Failed to create query vector."}

    initial_results = search_knn(r, query_vec, k=top_k, query_type=mtype)
    

    expanded_results = search.search_with_graph_expansion(
        initial_results, semantic_graph, r, k=top_k
    )

    return {"results": expanded_results}


@app.get("/graph")
async def get_graph():
    net = Network(height="100%", width="100%", bgcolor="#121212", font_color="white")
    net.barnes_hut(gravity=-2000, spring_length=200, spring_strength=0.02)

    type_colors = {"text": "#4db6ff", "image": "#76ff7a", "audio": "#ff9800"}

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
        html, body { margin: 0; padding: 0; height: 100%; overflow: hidden; background-color: #121212; }
        #mynetwork { width: 100%; height: 100vh !important; }
    </style>
    """
    html_content = html_content.replace("</head>", full_screen_css + "</head>")
    return HTMLResponse(content=html_content)

@app.get("/graph-data")
async def get_graph_data():
    nodes_data = []
    valid_node_ids = set()

    pipe = r.pipeline(transaction=False)
    for node_id in semantic_graph.nodes:
        pipe.hgetall(node_id)
    
    redis_results = pipe.execute()

    for i, node_id in enumerate(semantic_graph.nodes):
        redis_data = redis_results[i]
        
        data_val = redis_data.get(b'data')
        type_val = redis_data.get(b'type')

        if data_val and type_val:
            nodes_data.append({
                "id": node_id,
                "data": data_val.decode('utf-8'),
                "type": type_val.decode('utf-8')
            })
            valid_node_ids.add(node_id)
    
    edges_data = []
    for u, v, data in semantic_graph.edges(data=True):
        if u in valid_node_ids and v in valid_node_ids:
            edges_data.append({
                "from": u,
                "to": v,
                "score": data.get("score", 0)
            })
        
    return JSONResponse(content={"nodes": nodes_data, "edges": edges_data})

def search_knn(r, query_vector, k=5, query_id=None, query_type=None):
    query_vector_bytes = vector_to_bytes(query_vector)
    q = (
        Query(f"*=>[KNN {k*6} @embedding $vector AS vector_score]")
        .sort_by("vector_score")
        .return_fields("id", "data", "type", "vector_score")
        .dialect(2)
    )
    params = {"vector": query_vector_bytes}
    results = r.ft("idx:docs").search(q, query_params=params)

    same_mod = []
    cross_mod = []

    for doc in results.docs:
        similarity = 1 - float(doc.vector_score)

        if query_id and doc.id == query_id:
            similarity = 1.0

        doc_type = doc.type

        # Split results
        if query_type and doc_type != query_type:
            cross_mod.append({
                "id": doc.id,
                "data": doc.data,
                "type": doc.type,
                "score": similarity
            })
        else:
            same_mod.append({
                "id": doc.id,
                "data": doc.data,
                "type": doc.type,
                "score": similarity
            })

    # Sort by similarity
    same_mod.sort(key=lambda x: x["score"], reverse=True)
    cross_mod.sort(key=lambda x: x["score"], reverse=True)

    same_keep = same_mod[:k // 2] 
    cross_keep = cross_mod[:k // 2] 

    final_results = (same_keep + cross_keep)[:k]
    final_results.sort(key=lambda x: x["score"], reverse=True)

    return final_results



def update_graph_connections(graph: nx.Graph, source_key: str, neighbors: list[dict]):
    graph.add_node(source_key)
    source_type_bytes = r.hget(source_key, "type")
    source_type = source_type_bytes.decode() if source_type_bytes else None

    for n in neighbors:
        target_id = n["id"]
        if target_id == source_key:
            continue

        target_type_bytes = r.hget(target_id, "type")
        target_type = target_type_bytes.decode() if target_type_bytes else None

        score = n["score"]
        if source_type and target_type and source_type != target_type:
            score = max(score, 0.8) 

        graph.add_node(target_id)
        graph.add_edge(source_key, target_id, score=score)

    save_graph()
    print(f"✅ Graph updated: {source_key} connected to {len(neighbors)} neighbors (boosted cross-modal).")


def generate_hash(data) -> str:
    if isinstance(data, str):
        encoded_data = data.encode('utf-8')
    else:
        encoded_data = data
    return hashlib.sha256(encoded_data).hexdigest()


def vector_to_bytes(vector: List[float]) -> bytes:
    return np.array(vector, dtype=np.float32).tobytes()
