import json
import osmnx as ox
import networkx as nx
import numpy as np
from scipy.spatial import KDTree
import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.data import Data, Dataset, DataLoader
from pointer_model import PointerGNN  # Архитектура GNN-pointer

# 1. Загрузка контейнеров
with open('D:\\VSCODE\\Deeplom\\.Close-to-the-Truth-For-Test-GPT_new_model\\data\\updated_containers.json', 'r', encoding='utf-8') as f:
    containers = json.load(f)
#----------------------------------------------------------------------------#
# 2. Загрузка графа дорог
city_name = 'Улан-Удэ, Россия'
G_road = ox.graph_from_place(city_name, network_type='drive', simplify=True)
nodes_gdf = ox.graph_to_gdfs(G_road, nodes=True, edges=False)
nodes_list = list(G_road.nodes())  # фиксированный порядок узлов

# 3. Привязка контейнеров к ближайшим узлам
node_coords = np.array([[row.y, row.x] for row in nodes_gdf.itertuples()])
cont_coords = np.array([[c['latitude'], c['longitude']] for c in containers])
tree = KDTree(node_coords)
_, idxs = tree.query(cont_coords)
for i, c in enumerate(containers):
    c['nearest_node'] = int(nodes_gdf.index[idxs[i]])

# 4. Построение признаков узлов
node_features = []
for node in nodes_list:
    data = G_road.nodes[node]
    lat, lon = data['y'], data['x']
    deg = G_road.degree[node]
    fills = [c['fill_percentage'] for c in containers if c['nearest_node'] == node]
    avg_fill = np.mean(fills) if fills else 0.0
    node_features.append([lat, lon, deg, avg_fill])
x_base = torch.tensor(node_features, dtype=torch.float)

# 5. Построение рёбер
edge_index = torch.tensor(
    [[nodes_list.index(u), nodes_list.index(v)] for u, v in G_road.edges()],
    dtype=torch.long
).t().contiguous()

# 6. Генерация эталонных маршрутов (Nearest Neighbor) и примеров

def nearest_neighbor(nodes_ids, start_id):
    unvisited = set(nodes_ids)
    route = [start_id]
    current = start_id
    while unvisited:
        next_node = min(
            unvisited,
            key=lambda n: nx.shortest_path_length(G_road, current, n, weight='length')
        )
        route.append(next_node)
        unvisited.remove(next_node)
        current = next_node
    return route

pick_nodes = list({c['nearest_node'] for c in containers})
start_node = pick_nodes[0]
route = nearest_neighbor(pick_nodes, start_node)

train_examples = []
remaining = set(route[1:])
current = start_node
for next_node in route[1:]:
    mask = torch.tensor([1 if node_id in remaining else 0 for node_id in nodes_list], dtype=torch.float)
    is_curr = torch.tensor([1 if node_id == current else 0 for node_id in nodes_list], dtype=torch.float)
    x_aug = torch.cat([x_base, is_curr.unsqueeze(1), mask.unsqueeze(1)], dim=1)
    data = Data(x=x_aug, edge_index=edge_index)
    target_idx = nodes_list.index(next_node)
    train_examples.append((data, target_idx))
    remaining.remove(next_node)
    current = next_node

# 7. Dataset и DataLoader
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

# 8. Модель, оптимизатор, лосс
in_channels = x_base.shape[1] + 2
model = PointerGNN(in_channels=in_channels, hidden_channels=64)
optimizer = optim.Adam(model.parameters(), lr=0.005)
criterion = nn.CrossEntropyLoss()

# 9. Цикл обучения
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
#----------------------------------------------------------------------------#
# 10. Сохранение модели
torch.save(model.state_dict(), 'D:\\VSCODE\\Deeplom\\.Close-to-the-Truth-For-Test-GPT_new_model\\py\\pointer_gnn_model.pt')
print("Trained pointer-GNN saved to pointer_gnn_model.pt")
