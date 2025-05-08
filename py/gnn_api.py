from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from threading import Thread, Event
from algorithms import RouteAlgorithms
import time

# === Конфигурация ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTAINERS_PATH = os.path.join(BASE_DIR, '..', 'data', 'updated_containers.json')

# === Инициализация приложения ===
app = Flask(__name__)
CORS(app)

# Глобальные переменные
route_algorithms = None
initialization_complete = Event()

def background_initialization():
    """Фоновая инициализация ресурсов"""
    global route_algorithms
    print("Начало фоновой инициализации...")
    
    try:
        route_algorithms = RouteAlgorithms(CONTAINERS_PATH)
        initialization_complete.set()
        print("Фоновая инициализация завершена")
    except Exception as e:
        print(f"Ошибка инициализации: {str(e)}")

def wait_for_initialization(timeout=30):
    """Ожидание завершения инициализации"""
    if not initialization_complete.wait(timeout=timeout):
        raise RuntimeError("Инициализация не завершена за отведенное время")

# Запускаем инициализацию в фоне
Thread(target=background_initialization).start()

@app.before_request
def before_first_request():
    """Проверяем готовность перед обработкой запроса"""
    if request.method == 'OPTIONS':
        return
    
    try:
        wait_for_initialization()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503

# === Endpoints ===
@app.route('/gnn-optimize', methods=['POST'])
def gnn_optimize():
    try:
        data = request.get_json()
        containers = data.get('containers', [])
        
        result = route_algorithms.gnn_optimize(containers)
        return jsonify(result)
        
    except Exception as e:
        print("Ошибка в /gnn-optimize:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/route/ant_colony', methods=['POST'])
def ant_colony_route():
    try:
        result = route_algorithms.ant_colony_optimization()
        return jsonify(result)
    except Exception as e:
        print("Ошибка в муравьином алгоритме:", str(e))
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
    try:
        data = request.get_json()
        result = route_algorithms.clarke_wright()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Проверка состояния сервера"""
    status = {
        'algorithms_ready': initialization_complete.is_set(),
        'initialization_in_progress': not initialization_complete.is_set()
    }
    return jsonify(status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)