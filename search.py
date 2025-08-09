from redis.commands.search.query import Query
import numpy as np
from typing import List, Dict

def search_with_graph_expansion(initial_results, graph, r, k=10, depth=1):
    expanded_results = {item['id']: item for item in initial_results}
    
    queue = list(initial_results)

    for _ in range(depth):
        if not queue:
            break
        
        current_node_item = queue.pop(0)
        node_id = current_node_item['id']

        if node_id in graph:
            for neighbor_id in graph.neighbors(node_id):
                if neighbor_id not in expanded_results:
                    neighbor_data_bytes = r.hgetall(neighbor_id)
                    
                    if neighbor_data_bytes:
                        # Decode byte data from Redis
                        data_val = neighbor_data_bytes.get(b'data')
                        type_val = neighbor_data_bytes.get(b'type')

                        if data_val and type_val:
                            edge_data = graph.get_edge_data(node_id, neighbor_id)
                            original_score = current_node_item.get('score', 0.5)
                            edge_weight = edge_data.get('score', 0.5)
                            new_score = original_score * edge_weight * 0.9 

                            neighbor_item = {
                                "id": neighbor_id,
                                "data": data_val.decode('utf-8'),
                                "type": type_val.decode('utf-8'),
                                "score": new_score
                            }
                            expanded_results[neighbor_id] = neighbor_item
                            queue.append(neighbor_item)

    final_list = sorted(expanded_results.values(), key=lambda x: x['score'], reverse=True)
    return final_list[:k]


def vector_to_bytes(vector: List[float]) -> bytes:
    return np.array(vector, dtype=np.float32).tobytes()