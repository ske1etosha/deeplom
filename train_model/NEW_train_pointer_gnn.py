import json
import osmnx as ox
import networkx as nx
import numpy as np
from scipy.spatial import KDTree
import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.data import Data, Dataset, DataLoader
from datetime import datetime
import sys
import os
# Добавляем путь к проекту в PYTHONPATH
project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_path)
# Теперь импорт должен работать
from train_model.pointer_model import PointerGNN

def log_step(message):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")


# 1. Загрузка контейнеров (без изменений)
with open('data\\updated_containers.json', 'r', encoding='utf-8') as f:
    containers = json.load(f)
print("containers: ", containers[0])
log_step("1-st step done")


# 2. Загрузка графа дорог (без изменений)
city_name = 'Улан-Удэ, Россия'
G_road = ox.graph_from_place(city_name, network_type='drive', simplify=True)
nodes_gdf = ox.graph_to_gdfs(G_road, nodes=True, edges=False)
nodes_list = list(G_road.nodes())
log_step("2-nd step done")

# 3. Привязка контейнеров к узлам (без изменений)
node_coords = np.array([[row.y, row.x] for row in nodes_gdf.itertuples()])
cont_coords = np.array([[c['latitude'], c['longitude']] for c in containers])
tree = KDTree(node_coords)
_, idxs = tree.query(cont_coords)
for i, c in enumerate(containers):
    c['nearest_node'] = int(nodes_gdf.index[idxs[i]])
log_step("3-rd step done")

# 4. Построение признаков узлов (без изменений)
node_features = []
for node in nodes_list:
    data = G_road.nodes[node]
    lat, lon = data['y'], data['x']
    deg = G_road.degree[node]
    fills = [c['fill_percentage'] for c in containers if c['nearest_node'] == node]
    avg_fill = np.mean(fills) if fills else 0.0
    node_features.append([lat, lon, deg, avg_fill])
x_base = torch.tensor(node_features, dtype=torch.float)
log_step("4-th step done")

# 5. Построение рёбер (без изменений)
edge_index = torch.tensor(
    [[nodes_list.index(u), nodes_list.index(v)] for u, v in G_road.edges()],
    dtype=torch.long
).t().contiguous()
log_step("5-th step done")

# 6. НОВАЯ ВЕРСИЯ: Генерация эталонных маршрутов (Clarke-Wright)
def clarke_wright_route(nodes_ids, start_id, G):
    """Генерация маршрута по алгоритму Кларка-Райта"""
    if len(nodes_ids) == 1:
        return [start_id, nodes_ids[0], start_id] if nodes_ids[0] != start_id else [start_id, start_id]
    
    # Создаем матрицу расстояний
    distance_matrix = {
        (u, v): nx.shortest_path_length(G, u, v, weight='length')
        for u in nodes_ids for v in nodes_ids if u != v
    }
    
    # Рассчитываем savings
    savings = []
    depot = start_id
    nodes = [n for n in nodes_ids if n != depot]
    
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            u, v = nodes[i], nodes[j]
            saving = (distance_matrix.get((depot, u), 1e9) +
                     distance_matrix.get((depot, v), 1e9) -
                     distance_matrix.get((u, v), 1e9))
            savings.append((saving, u, v))
    
    savings.sort(reverse=True, key=lambda x: x[0])
    
    # Инициализация маршрутов
    routes = [[n] for n in nodes]
    
    # Объединение маршрутов
    for saving, u, v in savings:
        route_u, route_v = None, None
        
        for route in routes:
            if route[0] == u or route[-1] == u:
                route_u = route
            if route[0] == v or route[-1] == v:
                route_v = route
        
        if route_u is not None and route_v is not None and route_u is not route_v:
            # Проверяем возможность объединения
            if route_u[-1] == u and route_v[0] == v:
                new_route = route_u + route_v
            elif route_u[0] == u and route_v[-1] == v:
                new_route = route_v + route_u
            elif route_u[-1] == u and route_v[-1] == v:
                new_route = route_u + route_v[::-1]
            elif route_u[0] == u and route_v[0] == v:
                new_route = route_u[::-1] + route_v
            else:
                continue
            
            routes.remove(route_u)
            routes.remove(route_v)
            routes.append(new_route)
            if len(routes) == 1:
                break
    
    # Формируем финальный маршрут
    if not routes:
        return [depot, depot]
    
    final_route = [depot] + routes[0] + [depot] if routes else [depot, depot]
    return final_route
log_step("6-th step done")

# 7. Генерация обучающих примеров (множество маршрутов CW)
def generate_cw_examples(pick_nodes, G_road, num_samples):
    examples = []
    for i in range(num_samples):
        # Вариация стартовой точки
        start_node = np.random.choice(pick_nodes) if len(pick_nodes) > 1 else pick_nodes[0]
        route = clarke_wright_route(pick_nodes, start_node, G_road)
        
        remaining = set(route[1:-1])  # Исключаем депо
        current = start_node
        
        for next_node in route[1:]:
            if next_node == start_node:  # Пропускаем возврат в депо
                continue
                
            mask = torch.tensor([1 if node_id in remaining else 0 for node_id in nodes_list], dtype=torch.float)
            is_curr = torch.tensor([1 if node_id == current else 0 for node_id in nodes_list], dtype=torch.float)
            x_aug = torch.cat([x_base, is_curr.unsqueeze(1), mask.unsqueeze(1)], dim=1)
            data = Data(x=x_aug, edge_index=edge_index)
            target_idx = nodes_list.index(next_node)
            examples.append((data, target_idx))
            
            if next_node in remaining:
                remaining.remove(next_node)
            current = next_node
        print(i)
    return examples

pick_nodes = list({c['nearest_node'] for c in containers})
train_examples = generate_cw_examples(pick_nodes, G_road, num_samples=1)
log_step(f"7-th step done: generated {len(train_examples)} training examples")

# 8. Dataset и DataLoader
class RouteDataset(Dataset):
    def __init__(self, examples):
        self.examples = examples
    def __len__(self):
        return len(self.examples)
    def __getitem__(self, idx):
        data, target = self.examples[idx]
        return data, torch.tensor(target, dtype=torch.long)

dataset = RouteDataset(train_examples)
loader = DataLoader(dataset, batch_size=16, shuffle=True)
log_step("8-th step done")

# 9. Модель, оптимизатор, лосс
in_channels = x_base.shape[1] + 2
model = PointerGNN(in_channels=in_channels, hidden_channels=64)
optimizer = optim.Adam(model.parameters(), lr=0.005)
criterion = nn.CrossEntropyLoss()
log_step("9-th step done")

# 10. Цикл обучения
model.train()
for epoch in range(1, 51):
    total_loss = 0.0
    for data_batch, target_batch in loader:
        optimizer.zero_grad()
        out = model(data_batch)
        loss = criterion(out, target_batch)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    avg_loss = total_loss / len(loader)
    print(f"Epoch {epoch:02d} | Loss: {avg_loss:.4f}")
log_step("10-th step done")

# 11. Сохранение модели
torch.save(model.state_dict(), 'train_model\\trained_model.pt')
print("Trained pointer-GNN saved to trained_model.pt")