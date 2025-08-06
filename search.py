from redis.commands.search.query import Query
import numpy as np
from typing import List, Dict

def hybrid_search(r, query_vector, query_text=None, k=5, alpha=0.7):
    vector_bytes = vector_to_bytes(query_vector)

    vector_q = (
        Query(f"*=>[KNN {k*3} @embedding $vector AS vector_score]")
        .sort_by("vector_score")
        .return_fields("id", "data", "type", "vector_score")
        .dialect(2)
    )
    vec_results = r.ft("idx:docs").search(vector_q, query_params={"vector": vector_bytes})
    vec_dict = {doc.id: float(doc.vector_score) for doc in vec_results.docs}

    if not query_text:
        return [
            {
                "id": doc.id,
                "data": doc.data,
                "type": doc.type,
                "score": float(doc.vector_score)
            }
            for doc in vec_results.docs[:k]
        ]

    keyword_q = Query(f"@data:{query_text}").return_fields("id", "data", "type").dialect(2)
    keyword_results = r.ft("idx:docs").search(keyword_q)
    keyword_dict = {doc.id: 1.0 for doc in keyword_results.docs}  # binary score for match

    combined_scores = {}
    for doc_id in set(vec_dict.keys()) | set(keyword_dict.keys()):
        vec_score = vec_dict.get(doc_id, 0.0)
        kw_score = keyword_dict.get(doc_id, 0.0)
        combined = alpha * vec_score + (1 - alpha) * kw_score
        combined_scores[doc_id] = combined

    sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)

    final_results = []
    for doc_id, score in sorted_results[:k]:
        data_val = r.hget(doc_id, "data")
        type_val = r.hget(doc_id, "type")
        final_results.append({
            "id": doc_id,
            "data": data_val.decode() if data_val else None,
            "type": type_val.decode() if type_val else None,
            "score": score
        })

    return final_results

def vector_to_bytes(vector: List[float]) -> bytes:
    return np.array(vector, dtype=np.float32).tobytes()