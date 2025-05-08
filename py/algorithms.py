import json
import random
import numpy as np
from typing import List, Dict, Tuple
from scipy.spatial import KDTree
import networkx as nx
import osmnx as ox
import torch
import torch.nn.functional as F
from torch_geometric.data import Data
import os
import time

class RouteAlgorithms:
    def __init__(self, json_file: str, city: str = "Улан-Удэ, Россия"):
        self.containers = self.load_containers(json_file)
        self.city = city
        self.G_road = self.load_road_graph()
        self.nodes_gdf = ox.graph_to_gdfs(self.G_road, nodes=True, edges=False)
        self.nodes_list = list(self.G_road.nodes())
        self.node_coords = np.array([[row.y, row.x] for row in self.nodes_gdf.itertuples()])
        self.tree = KDTree(self.node_coords)
        self.attach_nearest_nodes()
        self.distance_matrix = self.calculate_distance_matrix()
        self.x_base = None
        self.edge_index = None
        self.gnn_model = None

    def calculate_metrics(self, route_nodes):
        """Вычисляет метрики для маршрута"""
        if not route_nodes or len(route_nodes) < 2:
            return {
                'distance': 0,
                'estimated_time': 0,
                'containers_served': 0
            }
        
        # Расчет общего расстояния
        total_distance = 0
        for i in range(len(route_nodes)-1):
            total_distance += self.distance_matrix.get((route_nodes[i], route_nodes[i+1]), 0)
        
        # Расчет времени (предположим скорость 40 км/ч ~ 11.11 м/с)
        speed_mps = 11.11  # метров в секунду
        unloading_time_per_container = 15 * 60  # 15 минут в секундах
        travel_time = total_distance / speed_mps
        total_time = travel_time + (len(route_nodes) * unloading_time_per_container)
        
        return {
            'distance': total_distance,  # в метрах
            'estimated_time': total_time,  # в секундах
            'containers_served': len(route_nodes)
        }

    def load_containers(self, json_file: str) -> List[Dict]:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Файл не найден: {json_file}")
            return []
        except json.JSONDecodeError:
            print(f"Ошибка парсинга JSON в файле: {json_file}")
            return []
        except UnicodeDecodeError:
            print(f"Ошибка кодировки файла: {json_file}. Убедитесь, что файл в UTF-8")
            return []

    def load_road_graph(self):
        print(f"Загрузка графа OSM для {self.city}")
        return ox.graph_from_place(self.city, network_type='drive', simplify=True)

    def attach_nearest_nodes(self, containers=None):
        containers = containers or self.containers
        cont_coords = np.array([[c['latitude'], c['longitude']] for c in containers])
        _, idxs = self.tree.query(cont_coords)
        for i, c in enumerate(containers):
            c['nearest_node'] = self.nodes_list[idxs[i]]
        return containers

    def calculate_distance_matrix(self) -> Dict[Tuple[int, int], float]:
        distance_matrix = {}
        nodes = list({c['nearest_node'] for c in self.containers})

        for i, u in enumerate(nodes):
            for j, v in enumerate(nodes):
                if i != j:
                    try:
                        distance = nx.shortest_path_length(self.G_road, u, v, weight='length')
                        distance_matrix[(u, v)] = distance
                    except:
                        distance_matrix[(u, v)] = 1e9
        return distance_matrix

    def get_route_coordinates(self, route_nodes: List[int]) -> List[List[float]]:
        route_coords = []
        for u, v in zip(route_nodes, route_nodes[1:]):
            try:
                path = nx.shortest_path(self.G_road, u, v, weight='length')
                for i in range(len(path) - 1):
                    a, b = path[i], path[i+1]
                    edge_data = self.G_road.get_edge_data(a, b)
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
                            y_a, x_a = self.G_road.nodes[a]['y'], self.G_road.nodes[a]['x']
                            y_b, x_b = self.G_road.nodes[b]['y'], self.G_road.nodes[b]['x']
                            route_coords.append([y_a, x_a])
                            route_coords.append([y_b, x_b])
            except Exception as e:
                print(f"Ошибка построения пути от {u} к {v}: {e}")
        return route_coords
#=======================================Муравьиный=============================================#
    def ant_colony_optimization(self, n_ants: int = 10, n_iterations: int = 100) -> Dict:
        start_time = time.time()

        nodes = list({c['nearest_node'] for c in self.containers})
        if len(nodes) < 2:
            return {'routes': []}

        best_path = None
        best_length = float('inf')

        for u in nodes:
            for v in nodes:
                if u != v and (u, v) not in self.distance_matrix:
                    self.distance_matrix[(u, v)] = 1e9

        pheromone = {}
        for u in nodes:
            for v in nodes:
                if u != v:
                    pheromone[(u, v)] = 1.0 / (self.distance_matrix.get((u, v), 1e9) + 1e-10)

        for iteration in range(n_iterations):
            ant_paths = []
            ant_lengths = []

            for _ in range(n_ants):
                current_node = random.choice(nodes)
                path = [current_node]
                visited = {current_node}
                path_length = 0.0

                while len(path) < len(nodes):
                    unvisited = [v for v in nodes if v not in visited]
                    if not unvisited:
                        break

                    probabilities = []
                    total = 0.0

                    for v in unvisited:
                        tau = pheromone[(current_node, v)]
                        eta = 1.0 / (self.distance_matrix[(current_node, v)] + 1e-10)
                        p = tau * eta
                        probabilities.append(p)
                        total += p

                    if total <= 0:
                        next_node = random.choice(unvisited)
                    else:
                        probabilities = [p/total for p in probabilities]
                        next_node = np.random.choice(unvisited, p=probabilities)

                    path.append(next_node)
                    path_length += self.distance_matrix[(current_node, next_node)]
                    visited.add(next_node)
                    current_node = next_node

                if len(path) > 1:
                    path_length += self.distance_matrix[(path[-1], path[0])]
                    ant_paths.append(path)
                    ant_lengths.append(path_length)

                    if path_length < best_length:
                        best_length = path_length
                        best_path = path.copy()

            for u in nodes:
                for v in nodes:
                    if u != v:
                        pheromone[(u, v)] *= 0.5

            for path, length in zip(ant_paths, ant_lengths):
                for i in range(len(path)-1):
                    pheromone[(path[i], path[i+1])] += 1.0 / (length + 1e-10)
                if len(path) > 1:
                    pheromone[(path[-1], path[0])] += 1.0 / (length + 1e-10)

        if best_path is None:
            return {'routes': []}

        route_coords = self.get_route_coordinates(best_path)
        route_containers = [c for c in self.containers if c['nearest_node'] in best_path]

        execution_time = time.time() - start_time
        metrics = self.calculate_metrics(best_path)

        response = {
            'routes': [{
                'points': [[float(x), float(y)] for x, y in route_coords],
                'nodes': [int(node) for node in best_path],
                'containers': [
                    {
                        'id': int(c['id']),
                        'latitude': float(c['latitude']),
                        'longitude': float(c['longitude']),
                    }
                    for c in route_containers
                ]
            }],
            'metrics': {
                'execution_time': execution_time,  # время работы алгоритма
                **metrics  # остальные метрики
            }
        }
        return response
#=======================================Генетический=============================================#
    def genetic_algorithm(self, population_size: int = 50, generations: int = 200) -> Dict:
        
        start_time = time.time()

        nodes = list({c['nearest_node'] for c in self.containers})
        if not nodes:
            return {'routes': []}

        def create_individual():
            individual = nodes.copy()
            random.shuffle(individual)
            return individual

        def calculate_fitness(individual):
            total = 0.0
            for i in range(len(individual)-1):
                total += self.distance_matrix.get((individual[i], individual[i+1]), 1e9)
            if len(individual) > 1:
                total += self.distance_matrix.get((individual[-1], individual[0]), 1e9)
            return 1 / (total + 1e-10)

        def crossover(parent1, parent2):
            size = len(parent1)
            child = [-1] * size
            start, end = sorted([random.randint(0, size-1) for _ in range(2)])

            for i in range(start, end+1):
                child[i] = parent1[i]

            pointer = (end + 1) % size
            for gene in parent2:
                if gene not in child:
                    child[pointer] = gene
                    pointer = (pointer + 1) % size

            return child

        def mutate(individual):
            if random.random() < 0.1:
                i, j = random.sample(range(len(individual)), 2)
                individual[i], individual[j] = individual[j], individual[i]
            return individual

        population = [create_individual() for _ in range(population_size)]

        for _ in range(generations):
            population = sorted(population, key=calculate_fitness, reverse=True)
            next_generation = population[:5]

            for _ in range(population_size - 5):
                parent1, parent2 = random.choices(population[:20], k=2)
                child = crossover(parent1, parent2)
                child = mutate(child)
                next_generation.append(child)

            population = next_generation

        best_individual = max(population, key=calculate_fitness)
        route_coords = self.get_route_coordinates(best_individual)
        route_containers = [c for c in self.containers if c['nearest_node'] in best_individual]

        execution_time = time.time() - start_time
        metrics = self.calculate_metrics(best_individual)

        return {
        'routes': [{
            'points': route_coords,
            'nodes': best_individual,
            'containers': route_containers
        }],
        'metrics': {
            'execution_time': execution_time,
            **metrics
        }
    }
#=======================================Муравьиный=============================================#
    def clarke_wright(self) -> Dict:

        start_time = time.time()

        nodes = list({c['nearest_node'] for c in self.containers})
        if not nodes:
                return {'routes': [], 'metrics': {
                'execution_time': 0,
                'distance': 0,
                'estimated_time': 0,
                'containers_served': 0
            }}

        try:
            if len(nodes) == 1:
                return self._single_node_route(nodes[0])
            else:
                depot = nodes[0]
                savings = []

                for i in range(1, len(nodes)):
                    for j in range(i+1, len(nodes)):
                        u, v = nodes[i], nodes[j]
                        saving = (self.distance_matrix.get((depot, u), 1e9) +
                                self.distance_matrix.get((depot, v), 1e9) -
                                self.distance_matrix.get((u, v), 1e9))
                        savings.append((saving, u, v))

                savings.sort(reverse=True, key=lambda x: x[0])

                routes = [[n] for n in nodes[1:]]

                for saving, u, v in savings:
                    route_u, route_v = None, None

                    for route in routes:
                        if route[0] == u or route[-1] == u:
                            route_u = route
                        if route[0] == v or route[-1] == v:
                            route_v = route

                    if route_u is not None and route_v is not None and route_u is not route_v:
                        new_route = self._merge_routes(route_u, route_v, u, v)
                        if new_route:
                            routes.remove(route_u)
                            routes.remove(route_v)
                            routes.append(new_route)
                            if len(routes) == 1:
                                break

                final_route = [depot] + routes[0] + [depot] if routes else [depot, depot]
                
                result = self._format_route_result(final_route)

            execution_time = time.time() - start_time
            metrics = self.calculate_metrics(result['routes'][0]['nodes'])

            result['metrics'] = {
                'execution_time': execution_time,
                **metrics
            }
            return result

        except Exception as e:
            print(f"Ошибка в алгоритме Кларка-Райта: {str(e)}")
            return {
                'routes': [], 
                'error': str(e),
                'metrics': {
                    'execution_time': time.time() - start_time,
                    'distance': 0,
                    'estimated_time': 0,
                    'containers_served': 0
                }
            }

    def _init_gnn_model(self):
        from pointer_model import PointerGNN
        
        node_features = []
        for node in self.nodes_list:
            data = self.G_road.nodes[node]
            lat, lon = data['y'], data['x']
            deg = self.G_road.degree[node]
            node_features.append([lat, lon, deg, 0.0])
        self.x_base = torch.tensor(node_features, dtype=torch.float)
        
        self.edge_index = torch.tensor(
            [[self.nodes_list.index(u), self.nodes_list.index(v)] for u, v in self.G_road.edges()],
            dtype=torch.long
        ).t().contiguous()
        
        self.gnn_model = PointerGNN(
            in_channels=self.x_base.shape[1] + 2,
            hidden_channels=64
        )
        model_path = 'py\pointer_gnn_model.pt'
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Модель не найдена по пути: {model_path}")
        self.gnn_model.load_state_dict(torch.load('py\pointer_gnn_model.pt', map_location='cpu'))
        self.gnn_model.eval()
        
    def gnn_optimize(self, containers=None):

        start_time = time.time()

        try:
            if not hasattr(self, 'x_base') or self.x_base is None:
                self._init_gnn_model()  # Явная инициализация при необходимости

            if containers is None:
                containers = self.containers
                
            containers = self.attach_nearest_nodes(containers)
            pick_nodes = list({c['nearest_node'] for c in containers})
            if not pick_nodes:
                return {
                    'routes': [],
                    'metrics': {
                        'execution_time': time.time() - start_time,
                        'distance': 0,
                        'estimated_time': 0,
                        'containers_served': 0
                    }
                }

            current = pick_nodes[0]
            remaining = set(pick_nodes) - {current}
            route = [current]

            while remaining:
                mask = torch.tensor(
                    [1 if n in remaining else 0 for n in self.nodes_list],
                    dtype=torch.float
                )
                is_curr = torch.tensor(
                    [1 if n == current else 0 for n in self.nodes_list],
                    dtype=torch.float
                )
                x_aug = torch.cat([self.x_base, is_curr.unsqueeze(1), mask.unsqueeze(1)], dim=1)
                graph_data = Data(x=x_aug, edge_index=self.edge_index)
                graph_data.batch = torch.zeros(graph_data.x.size(0), dtype=torch.long)

                with torch.no_grad():
                    logits = self.gnn_model(graph_data).squeeze(0)
                    probs = F.softmax(logits, dim=0)
                
                idxs = [self.nodes_list.index(n) for n in remaining]
                best_idx = idxs[torch.argmax(probs[idxs]).item()]
                next_node = self.nodes_list[best_idx]

                route.append(next_node)
                remaining.remove(next_node)
                current = next_node

            execution_time = time.time() - start_time
            result = self._format_route_result(route)
            metrics = self.calculate_metrics(route)

            result['metrics'] = {
                'execution_time': execution_time,
                **metrics
                }
            print(f"Metrics: {metrics}")
            return result
        except Exception as e:
            print("Ошибка в GNN оптимизации:", e)
            return {
                'routes': [], 
                'error': str(e),
                'metrics': {
                    'execution_time': time.time() - start_time,
                    'distance': 0,
                    'estimated_time': 0,
                    'containers_served': 0
                }
            }

    def _merge_routes(self, route1, route2, u, v):
        if route1[-1] == u and route2[0] == v:
            return route1 + route2
        elif route1[0] == u and route2[-1] == v:
            return route2 + route1
        elif route1[-1] == u and route2[-1] == v:
            return route1 + route2[::-1]
        elif route1[0] == u and route2[0] == v:
            return route2[::-1] + route1
        return None

    def _format_route_result(self, route_nodes):
        route_coords = self.get_route_coordinates(route_nodes)
        route_containers = [c for c in self.containers if c['nearest_node'] in route_nodes]
        metrics = self.calculate_metrics(route_nodes)
        
        return {
            'routes': [{
                'points': route_coords,
                'nodes': route_nodes,
                'containers': route_containers
            }],
            'metrics': metrics
        }


    def _single_node_route(self, node):
        route_coords = self.get_route_coordinates([node, node])
        route_containers = [c for c in self.containers if c['nearest_node'] == node]
        
        return {
            'routes': [{
                'points': route_coords,
                'nodes': [node, node],
                'containers': route_containers
            }],
            'metrics': {
                'distance': 0,
                'estimated_time': 15 * 60,  # только время выгрузки
                'containers_served': 1
            }
        }
    
    # В класс RouteAlgorithms добавляем новые методы
    def split_containers(self, n_routes=4):
        """Разделяет контейнеры на n маршрутов"""
        containers = sorted(self.containers, key=lambda x: x['fill_percentage'], reverse=True)
        return [containers[i::n_routes] for i in range(n_routes)]

    def calculate_metrics(self, route_nodes):
        """Вычисляет метрики для маршрута"""
        if not route_nodes or len(route_nodes) < 2:
            return {'distance': 0, 'time': 0}
        
        total_distance = 0
        for i in range(len(route_nodes)-1):
            total_distance += self.distance_matrix.get((route_nodes[i], route_nodes[i+1]), 0)
        
        # Предположим: скорость 40 км/ч = ~11.11 м/с и время выгрузки 5 мин на контейнер
        speed_mps = 11.11
        unloading_time = 5 * 60  # секунды
        
        total_time = (total_distance / speed_mps) + (len(route_nodes) * unloading_time)
        
        return {
            'distance': total_distance,
            'time': total_time,
            'containers_served': len(route_nodes)
        }