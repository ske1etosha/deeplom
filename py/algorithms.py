import json
import random
import math
import numpy as np
from typing import List, Dict, Tuple
import copy
from itertools import combinations
from scipy.spatial import KDTree
import networkx as nx
import osmnx as ox

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
    
    def attach_nearest_nodes(self):
        cont_coords = np.array([[c['latitude'], c['longitude']] for c in self.containers])
        _, idxs = self.tree.query(cont_coords)
        for i, c in enumerate(self.containers):
            c['nearest_node'] = self.nodes_list[idxs[i]]
    
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
                        # Если нет пути, используем большое число
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
    
    def ant_colony_optimization(self, n_ants: int = 10, n_iterations: int = 50) -> Dict:
        nodes = list({c['nearest_node'] for c in self.containers})
        if not nodes:
            return {'routes': []}

        try:
            n = len(nodes)
            if n == 1:
                return self._single_node_route(nodes[0])

            pheromone = {(u, v): 1.0 for u in nodes for v in nodes if u != v}
            best_path = None
            best_length = float('inf')

            for _ in range(n_iterations):
                paths = []
                lengths = []
                
                for _ in range(n_ants):
                    visited = set()
                    current = random.choice(nodes)
                    visited.add(current)
                    path = [current]
                    length = 0.0
                    
                    while len(path) < n:
                        unvisited = [v for v in nodes if v not in visited]
                        if not unvisited:
                            break
                        
                        probabilities = []
                        total = 0.0
                        
                        for v in unvisited:
                            tau = pheromone.get((current, v), 1.0)
                            eta = 1.0 / (self.distance_matrix.get((current, v), 1e9) + 1e-10)
                            p = tau * eta
                            probabilities.append(p)
                            total += p
                        
                        if total == 0:
                            next_node = random.choice(unvisited)
                        else:
                            probabilities = [p / total for p in probabilities]
                            next_node = np.random.choice(unvisited, p=probabilities)
                        
                        path.append(next_node)
                        length += self.distance_matrix.get((current, next_node), 1e9)
                        visited.add(next_node)
                        current = next_node
                    
                    if len(path) > 1:
                        length += self.distance_matrix.get((path[-1], path[0]), 1e9)
                        paths.append(path)
                        lengths.append(length)
                        
                        if length < best_length:
                            best_length = length
                            best_path = path.copy()
                
                # Обновление феромонов
                for u in nodes:
                    for v in nodes:
                        if u != v:
                            pheromone[(u, v)] *= 0.5  # Испарение
                
                for path, length in zip(paths, lengths):
                    for i in range(len(path)-1):
                        pheromone[(path[i], path[i+1])] += 1.0 / length
                    if len(path) > 1:
                        pheromone[(path[-1], path[0])] += 1.0 / length

            if not best_path:
                return {'routes': []}

            return self._format_route_result(best_path)

        except Exception as e:
            print(f"Ошибка в муравьином алгоритме: {str(e)}")
            return {'routes': [], 'error': str(e)}
    
    def genetic_algorithm(self, population_size: int = 50, generations: int = 200) -> Dict:
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
            if random.random() < 0.1:  # Вероятность мутации
                i, j = random.sample(range(len(individual)), 2)
                individual[i], individual[j] = individual[j], individual[i]
            return individual
        
        population = [create_individual() for _ in range(population_size)]
        
        for _ in range(generations):
            population = sorted(population, key=calculate_fitness, reverse=True)
            next_generation = population[:5]  # Элитные особи
            
            for _ in range(population_size - 5):
                parent1, parent2 = random.choices(population[:20], k=2)  # Турнирный отбор
                child = crossover(parent1, parent2)
                child = mutate(child)
                next_generation.append(child)
            
            population = next_generation
        
        best_individual = max(population, key=calculate_fitness)
        route_coords = self.get_route_coordinates(best_individual)
        route_containers = [c for c in self.containers if c['nearest_node'] in best_individual]
        
        return {
            'routes': [{
                'points': route_coords,
                'nodes': best_individual,
                'containers': route_containers
            }]
        }
    
    def clarke_wright(self) -> Dict:
        nodes = list({c['nearest_node'] for c in self.containers})
        if not nodes:
            return {'routes': []}

        try:
            if len(nodes) == 1:
                return self._single_node_route(nodes[0])

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
                    # Логика объединения маршрутов
                    new_route = self._merge_routes(route_u, route_v, u, v)
                    if new_route:
                        routes.remove(route_u)
                        routes.remove(route_v)
                        routes.append(new_route)
                        if len(routes) == 1:
                            break
            
            final_route = [depot] + routes[0] + [depot] if routes else [depot, depot]
            return self._format_route_result(final_route)

        except Exception as e:
            print(f"Ошибка в алгоритме Кларка-Райта: {str(e)}")
            return {'routes': [], 'error': str(e)}
    #==============================Вспомогалтельные функции======================================№  
    def _merge_routes(self, route1, route2, u, v):
        """Вспомогательная функция для объединения маршрутов"""
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
        """Форматирование результата для всех алгоритмов"""
        route_coords = self.get_route_coordinates(route_nodes)
        route_containers = [c for c in self.containers if c['nearest_node'] in route_nodes]
        
        return {
            'routes': [{
                'points': route_coords,
                'nodes': route_nodes,
                'containers': route_containers
            }]
        }

    def _single_node_route(self, node):
        """Обработка случая с одним узлом"""
        route_coords = self.get_route_coordinates([node, node])
        route_containers = [c for c in self.containers if c['nearest_node'] == node]
        
        return {
            'routes': [{
                'points': route_coords,
                'nodes': [node, node],
                'containers': route_containers
            }]
        }