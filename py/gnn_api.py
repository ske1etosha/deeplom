from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import osmnx as ox
import networkx as nx
import numpy as np
from scipy.spatial import KDTree
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
from pointer_model import PointerGNN

# === Инициализация приложения ===
app = Flask(__name__)
CORS(app)

# === Загружаем дорожной граф и данные ===
CITY = "Улан-Удэ, Россия"
print("Загрузка графа OSM для", CITY)
G_road = ox.graph_from_place(CITY, network_type='drive', simplify=True)
nodes_gdf = ox.graph_to_gdfs(G_road, nodes=True, edges=False)
nodes_list = list(G_road.nodes())

# Координаты узлов для KDTree
node_coords = np.array([[row.y, row.x] for row in nodes_gdf.itertuples()])
tree = KDTree(node_coords)

# Формируем базовые признаки узлов (lat, lon, degree, avg_fill=0)
node_features = []
for node in nodes_list:
    data = G_road.nodes[node]
    lat, lon = data['y'], data['x']
    deg = G_road.degree[node]
    node_features.append([lat, lon, deg, 0.0])
x_base = torch.tensor(node_features, dtype=torch.float)

# Формируем edge_index
edge_index = torch.tensor(
    [[nodes_list.index(u), nodes_list.index(v)] for u, v in G_road.edges()],
    dtype=torch.long
).t().contiguous()

# === Загружаем Pointer-GNN модель ===
print("Загрузка Pointer-GNN модели...")
in_channels = x_base.shape[1] + 2
model = PointerGNN(in_channels=in_channels, hidden_channels=64)
model.load_state_dict(torch.load('.gnn_routing_For-Test-GPT\py\pointer_gnn_model.pt', map_location='cpu'))
model.eval()
print("Модель готова к предсказаниям")

# === Вспомогательные функции ===
def attach_nearest_nodes(containers):
    cont_coords = np.array([[c['latitude'], c['longitude']] for c in containers])
    _, idxs = tree.query(cont_coords)
    for i, c in enumerate(containers):
        c['nearest_node'] = nodes_list[idxs[i]]
    return containers

# === Endpoint GNN-оптимизации ===
@app.route('/gnn-optimize', methods=['POST'])
def gnn_optimize():
    try:
        data = request.get_json()
        containers = data.get('containers', [])
        if not containers:
            return jsonify({'error': 'Нет контейнеров для оптимизации'}), 400

        attach_nearest_nodes(containers)
        pick_nodes = list({c['nearest_node'] for c in containers})
        if not pick_nodes:
            return jsonify({'routes': []})

        current = pick_nodes[0]
        remaining = set(pick_nodes) - {current}
        route = [current]

        while remaining:
            mask = torch.tensor([1 if n in remaining else 0 for n in nodes_list], dtype=torch.float)
            is_curr = torch.tensor([1 if n == current else 0 for n in nodes_list], dtype=torch.float)
            x_aug = torch.cat([x_base, is_curr.unsqueeze(1), mask.unsqueeze(1)], dim=1)
            graph_data = Data(x=x_aug, edge_index=edge_index)
            graph_data.batch = torch.zeros(graph_data.x.size(0), dtype=torch.long)

            with torch.no_grad():
                logits = model(graph_data).squeeze(0)
                probs = F.softmax(logits, dim=0)
            idxs = [nodes_list.index(n) for n in remaining]
            best_idx = idxs[torch.argmax(probs[idxs]).item()]
            next_node = nodes_list[best_idx]

            route.append(next_node)
            remaining.remove(next_node)
            current = next_node

        route_coords = []
        for u, v in zip(route, route[1:]):
            try:
                path = nx.shortest_path(G_road, u, v, weight='length')
                for i in range(len(path) - 1):
                    a, b = path[i], path[i+1]
                    edge_data = G_road.get_edge_data(a, b)
                    if edge_data:
                        if isinstance(edge_data, dict):
                            data_edge = edge_data[next(iter(edge_data))]
                        else:
                            data_edge = edge_data

                        if 'geometry' in data_edge:
                            coords = list(data_edge['geometry'].coords)
                            for lon, lat in coords:
                                route_coords.append([lat, lon])
                        else:
                            y_a, x_a = G_road.nodes[a]['y'], G_road.nodes[a]['x']
                            y_b, x_b = G_road.nodes[b]['y'], G_road.nodes[b]['x']
                            route_coords.append([y_a, x_a])
                            route_coords.append([y_b, x_b])
            except Exception as e:
                print(f"Ошибка построения пути от {u} к {v}: {e}")

        # Выделяем контейнеры, которые реально попали в маршрут
        route_containers = [c for c in containers if c['nearest_node'] in route]

        return jsonify({
            'routes': [
                {
                    'points': route_coords,
                    'nodes': route,
                    'containers': route_containers
                }
            ]
        })

    except Exception as e:
        print("Ошибка в /gnn-optimize:", e)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
