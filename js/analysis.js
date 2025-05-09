document.addEventListener('DOMContentLoaded', function() {
    if (typeof ymaps === 'undefined') {
        console.error('Yandex Maps API not loaded');
        return;
    }

    ymaps.ready(function() {
        try {
            const routesData = JSON.parse(localStorage.getItem('analysisData'));
            if (!routesData) {
                alert('Нет данных для анализа');
                window.location.href = 'index.html';
                return;
            }

            // Инициализация всех карт
            const maps = {
                gnn: initMap('gnn-map'),
                ant: initMap('ant-map'),
                genetic: initMap('genetic-map'),
                clarke: initMap('clarke-map')
            };

            // Отображение данных
            displayAnalysisData(routesData, maps);
        } catch (error) {
            console.error('Analysis error:', error);
            alert('Ошибка при анализе: ' + error.message);
        }
    });
});

function initMap(containerId) {
    const map = new ymaps.Map(containerId, {
        center: [51.8345, 107.5845],
        zoom: 13,
        controls: ['zoomControl', 'typeSelector']
    });
    console.log(`Map initialized in ${containerId}`); // Логирование
    return map;
}

function displayAnalysisData(routesData, maps) {
    const metricsBody = document.getElementById('metrics-body');
    metricsBody.innerHTML = '';

    Object.entries(routesData).forEach(([algorithm, data]) => {
        if (!data?.routes?.[0]?.points) {
            console.warn(`No route points for ${algorithm}`);
            return;
        }

        // Добавляем маршрут на карту
        const route = data.routes[0];
        const polyline = new ymaps.Polyline(route.points, {}, {
            strokeColor: '#4CAF50',
            strokeWidth: 5,
            strokeOpacity: 0.7
        });
        
        maps[algorithm].geoObjects.add(polyline);
        maps[algorithm].setBounds(polyline.geometry.getBounds());

        // Добавляем метрики в таблицу
        metricsBody.innerHTML += `
            <tr>
                <td>${getAlgorithmName(algorithm)}</td>
                <td>${(data.metrics.distance / 1000).toFixed(2)} км</td>
                <td>${data.metrics.execution_time.toFixed(2)} сек</td>
                <td>${Math.round(data.metrics.estimated_time / 60)} мин</td>
                <td>${data.metrics.containers_served}</td>
            </tr>
        `;
    });
}

function getAlgorithmName(key) {
    const names = {
        'gnn': 'GNN Оптимизация',
        'ant': 'Муравьиный алгоритм',
        'genetic': 'Генетический алгоритм',
        'clarke': 'Кларка-Райта'
    };
    return names[key] || key;
}

