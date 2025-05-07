from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pickle
from datetime import datetime, timedelta
from threading import Thread
from typing import List, Dict, Tuple
import numpy as np
from scipy.spatial import KDTree
import torch
import torch.nn.functional as F
from torch_geometric.data import Data

# Тяжелые импорты переносим в функции
# import osmnx as ox
# import networkx as nx
# from pointer_model import PointerGNN
# from algorithms import RouteAlgorithms

# === Конфигурация ===
CITY = "Улан-Удэ, Россия"
CACHE_DIR = "graph_cache"
CACHE_FILE = os.path.join(CACHE_DIR, "ulan_ude_graph.pickle")
CACHE_EXPIRE_DAYS = 7
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTAINERS_PATH = os.path.join(BASE_DIR, '..', 'data', 'updated_containers.json')

# === Инициализация приложения ===
app = Flask(__name__)
CORS(app)

# Глобальные переменные для хранения состояния
G_road = None
nodes_gdf = None
nodes_list = None
node_coords = None
tree = None
x_base = None
edge_index = None
model = None
route_algorithms = None

def load_or_download_graph():
    """Загрузка графа с кэшированием"""
    global G_road, nodes_gdf, nodes_list
    
    import osmnx as ox
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if os.path.exists(CACHE_FILE):
        mod_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        if datetime.now() - mod_time < timedelta(days=CACHE_EXPIRE_DAYS):
            with open(CACHE_FILE, 'rb') as f:
                print("Загружаем граф из кэша...")
                G_road = pickle.load(f)
                nodes_gdf = ox.graph_to_gdfs(G_road, nodes=True, edges=False)
                nodes_list = list(G_road.nodes())
                return

    print("Загрузка графа OSM (это может занять несколько минут)...")
    ox.config(use_cache=True, log_console=True)
    G_road = ox.graph_from_place(CITY, network_type='drive', simplify=True)
    nodes_gdf = ox.graph_to_gdfs(G_road, nodes=True, edges=False)
    nodes_list = list(G_road.nodes())
    
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(G_road, f)

def initialize_graph_data():
    """Инициализация данных графа"""
    global node_coords, tree, x_base, edge_index
    
    node_coords = np.array([[row.y, row.x] for row in nodes_gdf.itertuples()])
    tree = KDTree(node_coords)
    
    # Формируем базовые признаки узлов
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

def load_model():
    """Загрузка модели GNN"""
    global model
    from pointer_model import PointerGNN
    
    model_path = os.path.join(BASE_DIR, 'pointer_gnn_model.pt')
    print("Загрузка Pointer-GNN модели...")
    in_channels = x_base.shape[1] + 2
    model = PointerGNN(in_channels=in_channels, hidden_channels=64)
    model.load_state_dict(torch.load(model_path, map_location='cpu'))
    model.eval()
    print("Модель готова к предсказаниям")

def initialize_algorithms():
    """Инициализация алгоритмов маршрутизации"""
    global route_algorithms
    from algorithms import RouteAlgorithms
    route_algorithms = RouteAlgorithms(CONTAINERS_PATH)

def background_initialization():
    """Фоновая инициализация ресурсов"""
    print("Начало фоновой инициализации...")
    load_or_download_graph()
    initialize_graph_data()
    load_model()
    initialize_algorithms()
    print("Фоновая инициализация завершена")

# Запускаем инициализацию в фоне
Thread(target=background_initialization).start()

# === Вспомогательные функции ===
def attach_nearest_nodes(containers):
    """Привязка контейнеров к ближайшим узлам графа"""
    cont_coords = np.array([[c['latitude'], c['longitude']] for c in containers])
    _, idxs = tree.query(cont_coords)
    for i, c in enumerate(containers):
        c['nearest_node'] = nodes_list[idxs[i]]
    return containers

def get_route_coordinates(route_nodes):
    """Получение координат маршрута"""
    import networkx as nx
    
    route_coords = []
    for u, v in zip(route_nodes, route_nodes[1:]):
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
    return route_coords

# === Endpoints ===
@app.route('/gnn-optimize', methods=['POST'])
def gnn_optimize():
    """Endpoint для оптимизации маршрута GNN"""
    try:
        if model is None:
            return jsonify({'error': 'Модель еще не загружена'}), 503
            
        data = request.get_json()
        containers = data.get('containers', [])
        if not containers:
            return jsonify({'error': 'Нет контейнеров для оптимизации'}), 400

        containers = attach_nearest_nodes(containers)
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

        route_coords = get_route_coordinates(route)
        route_containers = [c for c in containers if c['nearest_node'] in route]

        return jsonify({
            'routes': [{
                'points': route_coords,
                'nodes': route,
                'containers': route_containers
            }]
        })

    except Exception as e:
        print("Ошибка в /gnn-optimize:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/route/ant_colony', methods=['POST'])
def ant_colony_route():
    """Endpoint для муравьиного алгоритма"""
    try:
        print("Запуск муравьиного алгоритма")  # Логирование
        result = route_algorithms.ant_colony_optimization()
        #print("Результат муравьиного алгоритма:", result)  # Логирование
        return jsonify(result)
    except Exception as e:
        print("Ошибка в муравьином алгоритме:", str(e))  # Логирование
        return jsonify({'error': str(e)}), 500

@app.route('/api/route/genetic', methods=['POST'])
def genetic_route():
    try:
        result = route_algorithms.genetic_algorithm()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/route/clarke_wright', methods=['POST'])
def clarke_wright_route():
    """Endpoint для алгоритма Кларка-Райта"""
    try:
        if route_algorithms is None:
            return jsonify({'error': 'Алгоритмы еще не инициализированы'}), 503
            
        data = request.get_json()
        max_containers = data.get('maxContainers', 20)
        result = route_algorithms.clarke_wright()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Проверка состояния сервера"""
    status = {
        'graph_loaded': G_road is not None,
        'model_loaded': model is not None,
        'algorithms_ready': route_algorithms is not None
    }
    return jsonify(status)

if __name__ == '__main__':
    # Минимальная инициализация перед запуском сервера
    load_or_download_graph()
    initialize_graph_data()
    
    # Запускаем сервер с возможностью горячей перезагрузки
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)