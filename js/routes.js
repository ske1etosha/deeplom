let routes = [];
let currentRouteIndex = -1;

async function optimizeRoutes() {
    if (containers.length === 0) {
        alert("Нет контейнеров для построения маршрута!");
        return;
    }

    const algorithm = document.getElementById("algorithm-select").value;

    try {
        let endpoint;
        const baseUrl = 'http://localhost:5000'; // Базовый URL Flask сервера
        
        switch(algorithm) {
            case 'ant':
                endpoint = `${baseUrl}/api/route/ant_colony`;
                break;
            case 'genetic':
                endpoint = `${baseUrl}/api/route/genetic`;
                break;
            case 'clarke':
                endpoint = `${baseUrl}/api/route/clarke_wright`;
                break;
            case 'gnn':
                endpoint = `${baseUrl}/gnn-optimize`;
                break;
            default:
                throw new Error('Неизвестный алгоритм');
        }

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ 
                containers: containers
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // if (!data.routes || data.routes.length === 0) {
        //     alert("Алгоритм не вернул ни одного маршрута.");
        //     return;
        // }

        // routes = data.routes.map((r, i) => {
        //     const containersForRoute = containers.filter(c =>
        //         r.nodes.includes(c.nearest_node)
        //     );
        //     return {
        //         index: i,
        //         containers: containersForRoute,
        //         routePoints: r.points,
        //         color: getRouteColor(i),
        //         metrics: data.metrics || {
        //             distance: 0,
        //             estimated_time: 0,
        //             containers_served: 0,
        //             execution_time: 0
        //         }
        //     };
        // });

        if (!data.routes || data.routes.length === 0) {
            alert("Алгоритм не вернул ни одного маршрута.");
            return;
        }
        
        // Нормализуем структуру данных
        routes = [{
            routePoints: data.routes[0].points,
            nodes: data.routes[0].nodes,
            containers: containers.filter(c => 
                data.routes[0].nodes.includes(c.nearest_node)
            ),
            color: getRouteColor(0),
            metrics: data.metrics || {
                distance: 0,
                estimated_time: 0,
                containers_served: 0,
                execution_time: 0
            }
        }];

        console.log("Маршруты получены:", routes);
        clearMap();
        updateRouteStats(data, getAlgorithmName(algorithm));
        showRoute(0);

    } catch (err) {
        console.error("Ошибка при оптимизации маршрута:", err);
        alert("Ошибка при оптимизации маршрута: " + err.message);
    }
}

function showRoute(index) {
    // Проверка наличия routes и корректности индекса
    if (!routes || !Array.isArray(routes) || routes.length === 0) {
        console.error("Маршруты не определены или пусты");
        alert("Нет данных о маршрутах");
        return;
    }

    if (index < 0 || index >= routes.length) {
        console.error(`Неверный индекс маршрута: ${index}`);
        alert("Выбран несуществующий маршрут");
        return;
    }

    const route = routes[index];
    currentRouteIndex = index;
    
    try {
        // Очищаем карту
        clearMap();

        // Проверяем наличие точек маршрута
        if (!route.routePoints || route.routePoints.length === 0) {
            throw new Error("Маршрут не содержит точек");
        }

        // Отрисовываем линию маршрута
        const polyline = new ymaps.Polyline(route.routePoints, {}, {
            strokeColor: route.color || '#FF0000',
            strokeWidth: 5,
            strokeOpacity: 0.8
        });
        map.geoObjects.add(polyline);

        // Центрируем карту на маршруте
        map.setBounds(polyline.geometry.getBounds());

        // Отображаем все контейнеры
        containers.forEach(container => {
            addPlacemark(container);
        });

        // Обновляем список контейнеров для маршрута
        if (route.containers && Array.isArray(route.containers)) {
            updateContainerList(route.containers);
        } else {
            console.warn("Маршрут не содержит данных о контейнерах");
        }

    } catch (error) {
        console.error("Ошибка при отображении маршрута:", error);
        alert("Ошибка при построении маршрута: " + error.message);
    }
}

function getRouteColor(index) {
    const colors = ['#FF0000', '#00FF00', '#0000FF', '#FF00FF', '#FFA500', '#00CED1'];
    return colors[index % colors.length];
}

function updateRouteStats(routeData, algorithmName) {
    if (!routeData || !routeData.metrics) return;
    
    const metrics = routeData.metrics;
    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.round(seconds % 60);
        return `${mins} мин ${secs} сек`;
    };

    document.getElementById('algorithm-name').textContent = algorithmName;
    document.getElementById('distance-value').textContent = `${(metrics.distance / 1000).toFixed(2)} км`;
    document.getElementById('execution-time').textContent = `${metrics.execution_time.toFixed(2)} сек`;
    document.getElementById('total-time').textContent = formatTime(metrics.estimated_time);
    document.getElementById('containers-count').textContent = `${metrics.containers_served} из ${containers.length}`;
}

function getAlgorithmName(value) {
    const names = {
        'gnn': 'GNN Оптимизация',
        'ant': 'Муравьиный алгоритм',
        'genetic': 'Генетический алгоритм',
        'clarke': 'Кларка-Райта'
    };
    return names[value] || value;
}

document.getElementById('analyze-btn').addEventListener('click', async function() {
    if (containers.length === 0) {
        alert('Нет контейнеров для анализа');
        return;
    }

    const analysisData = {};
    const algorithms = ['gnn', 'ant', 'genetic', 'clarke'];
    
    try {
        // Показываем индикатор загрузки
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Анализ...';
        this.disabled = true;
        
        // Запускаем все алгоритмы
        for (const algorithm of algorithms) {
            const endpoint = getAlgorithmEndpoint(algorithm);
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ containers: containers })
            });
            analysisData[algorithm] = await response.json();
        }
        
        // Сохраняем данные для страницы анализа
        localStorage.setItem('analysisData', JSON.stringify(analysisData));
        
        // Переходим на страницу анализа
        window.location.href = 'analysis.html';
        
    } catch (error) {
        console.error('Ошибка анализа:', error);
        alert('Ошибка при выполнении анализа');
    } finally {
        this.innerHTML = '<i class="fas fa-chart-line"></i> Анализ';
        this.disabled = false;
    }
});

function getAlgorithmEndpoint(algorithm) {
    const baseUrl = 'http://localhost:5000';
    switch(algorithm) {
        case 'ant': return `${baseUrl}/api/route/ant_colony`;
        case 'genetic': return `${baseUrl}/api/route/genetic`;
        case 'clarke': return `${baseUrl}/api/route/clarke_wright`;
        case 'gnn': return `${baseUrl}/gnn-optimize`;
        default: throw new Error('Неизвестный алгоритм');
    }
}