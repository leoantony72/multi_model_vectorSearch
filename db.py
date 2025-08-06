import redis
import numpy as np
from redisgraph import Graph
from typing import List, Dict, Any
from redis.commands.search.field import TextField, NumericField, TagField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

def storeVec(key: str, vector: list, data: str, r: redis.Redis, mtype: str):
    vecBytes = VectoBytes(vector)
    i = r.hset(key, mapping={
        "embedding": vecBytes,
        "data": data,
        "type": mtype
    })
    if i == 3:
        print(f"Stored {mtype} vector for key: {key}")
    else:
        print(f"Stored {i} fields for key: {key} (expected 3)")

def VectoBytes(vector: list[float]) -> bytes:
    return np.array(vector, dtype=np.float32).tobytes()



def create_index(r: redis.Redis, dim: int):
    try:
        r.ft("idx:docs").info()
        print("Index already exists.")
    except:
        schema = [
            TextField("id"),
            TextField("data"),
            TextField("type"),
            VectorField("embedding", "FLAT", {
                "TYPE": "FLOAT32",
                "DIM": dim,
                "DISTANCE_METRIC": "COSINE"
            })
        ]
        r.ft("idx:docs").create_index(schema)
        print(f"Index created with dimension {dim} and COSINE metric.")