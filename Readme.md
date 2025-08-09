# Real-Time Multi-Modal Semantic Search System

This project is a **real-time, multi-modal semantic search system** that combines **vector similarity search** with **graph-based context expansion**.  
It supports both **text** and **image** search using locally computed **CLIP embeddings**.

---

## 📜 What I Built
- **Local CLIP embeddings** for text and images (`openai/clip-vit-base-patch16`, 512-dim)
- **Redis 8 vector index** with cosine similarity and KNN search
- **Result caching** in Redis for low latency and reduced recompute
- **NetworkX semantic graph** to link and rank related items beyond the initial top-K  
  → enables richer, more explainable retrieval
- **Duplicate prevention** using SHA-256 content hashing
- **Endpoints** for:
  - `submit` (ingest)
  - `search` (retrieve)
- **Go API client** + **lightweight Python server** for embeddings

---

## 🛠 Architecture Overview
1. **Embed**: Text and images embedded locally via CLIP  
2. **Index**: Vectors stored in Redis 8 (cosine similarity)  
3. **Search**: Fast KNN lookups in Redis  
4. **Expand**: Related items discovered via semantic graph traversal in NetworkX  
5. **Cache**: Query results cached in Redis  
6. **Serve**: Go handles API layer; Python server handles embedding and indexing

---

## 🚀 Getting Started

### 1️⃣ Start the required services
```bash
docker-compose up -d
```

```bash
python app.py
```

```bash
fastapi dev main.py
```


### Running Addr
```bash
localhost:8000
```