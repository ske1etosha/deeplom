from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from threading import Thread, Event
from algorithms import RouteAlgorithms


# === Конфигурация ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTAINERS_PATH = os.path.join(BASE_DIR, '..', 'data', 'updated_containers.json')

# === Инициализация приложения ===
app = Flask(__name__)
CORS(app)

# Глобальные переменные
initialization_complete = Event()

def background_initialization():
    """Фоновая инициализация ресурсов"""
    global route_algorithms
    print("Начало фоновой инициализации...")
    
    try:
        #route_algorithms = RouteAlgorithms(CONTAINERS_PATH)
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
        file_name = data.get('fileName')  
        if not file_name:
            return jsonify({'error': 'Файл с контейнерами не указан'}), 400
        json_path = os.path.join(BASE_DIR, '..', 'data', file_name)
        if not os.path.isfile(json_path):
            return jsonify({'error': f'Файл не найден: {file_name}'}), 400
        route_algorithms = RouteAlgorithms(json_path)

        result = route_algorithms.gnn_optimize(containers)
        return jsonify(result)
        
    except Exception as e:
        print("Ошибка в /gnn-optimize:", e)
        return jsonify({'error': str(e)}), 500

@app.route('/api/route/ant_colony', methods=['POST'])
def ant_colony_route():
    try:
        data = request.get_json()
        file_name = data.get('fileName')  
        if not file_name:
            return jsonify({'error': 'Файл с контейнерами не указан'}), 400
        json_path = os.path.join(BASE_DIR, '..', 'data', file_name)
        if not os.path.isfile(json_path):
            return jsonify({'error': f'Файл не найден: {file_name}'}), 400
        route_algorithms = RouteAlgorithms(json_path)

        result = route_algorithms.ant_colony_optimization()
        return jsonify(result)
    except Exception as e:
        print("Ошибка в муравьином алгоритме:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/route/genetic', methods=['POST'])
def genetic_route():
    try:
        data = request.get_json()
        file_name = data.get('fileName')  
        if not file_name:
            return jsonify({'error': 'Файл с контейнерами не указан'}), 400
        json_path = os.path.join(BASE_DIR, '..', 'data', file_name)
        if not os.path.isfile(json_path):
            return jsonify({'error': f'Файл не найден: {file_name}'}), 400
        route_algorithms = RouteAlgorithms(json_path)

        result = route_algorithms.genetic_algorithm()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/route/clarke_wright', methods=['POST'])
def clarke_wright_route():
    try:
        data = request.get_json()
        file_name = data.get('fileName')  
        if not file_name:
            return jsonify({'error': 'Файл с контейнерами не указан'}), 400
        json_path = os.path.join(BASE_DIR, '..', 'data', file_name)
        if not os.path.isfile(json_path):
            return jsonify({'error': f'Файл не найден: {file_name}'}), 400
        route_algorithms = RouteAlgorithms(json_path)

        result = route_algorithms.clarke_wright()
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analysis', methods=['POST'])
def analysis():
    try:
        data = request.get_json()
        file_name = data.get('fileName')
        
        if not file_name:
            return jsonify({'error': 'Файл с контейнерами не указан'}), 400
            
        json_path = os.path.join(BASE_DIR, '..', 'data', file_name)
        if not os.path.isfile(json_path):
            return jsonify({'error': f'Файл не найден: {file_name}'}), 400
        
        # Создаем экземпляр RouteAlgorithms с указанным файлом
        route_algorithms = RouteAlgorithms(json_path)
        
        # Запускаем все алгоритмы параллельно для ускорения
        from concurrent.futures import ThreadPoolExecutor
        
        results = {}
        
        with ThreadPoolExecutor() as executor:
            # Запускаем все алгоритмы
            futures = {
                'ant_colony': executor.submit(route_algorithms.ant_colony_optimization),
                'genetic': executor.submit(route_algorithms.genetic_algorithm),
                'clarke_wright': executor.submit(route_algorithms.clarke_wright),
                'gnn': executor.submit(route_algorithms.gnn_optimize, data.get('containers', []))
            }
            
            # Ждем завершения всех алгоритмов
            for name, future in futures.items():
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = {'error': str(e)}
        
        return jsonify(results)
        
    except Exception as e:
        print(f"Ошибка в /api/analysis: {str(e)}")
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