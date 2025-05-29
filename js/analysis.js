document.addEventListener('DOMContentLoaded', function() {
    if (typeof ymaps === 'undefined') {
        console.error('Yandex Maps API not loaded');
        return;
    }

    ymaps.ready(async function() {
        try {
            // Получаем и проверяем сохраненные данные
            const requestDataJson = localStorage.getItem('analysisRequestData');
            if (!requestDataJson) {
                throw new Error('Не найдены параметры для анализа. Вернитесь на главную страницу.');
            }

            let requestData;
            try {
                requestData = JSON.parse(requestDataJson);
            } catch (e) {
                throw new Error('Неверный формат параметров анализа');
            }

            // Получаем данные для анализа с сервера
            const response = await fetch('http://localhost:5000/api/analysis', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData) // Преобразуем объект в JSON строку
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Ошибка сервера: ${response.status} - ${errorText}`);
            }

            const routesData = await response.json();
            console.log('Получены данные анализа:', routesData);

            // Проверяем структуру ответа
            if (!routesData || typeof routesData !== 'object') {
                throw new Error('Сервер вернул неверный формат данных');
            }

            // Инициализация всех карт
            const maps = {
                gnn: initMap('gnn-map'),
                ant_colony: initMap('ant-map'),
                genetic: initMap('genetic-map'),
                clarke_wright: initMap('clarke-map')
            };

            // Отображение данных
            displayAnalysisData(routesData, maps);
            
        } catch (error) {
            console.error('Analysis error:', error);
            alert('Ошибка при анализе: ' + error.message);
            window.location.href = 'index.html';
        }
    });
});

function initMap(containerId) {
    const map = new ymaps.Map(containerId, {
        center: [51.8345, 107.5845],
        zoom: 13,
        controls: ['zoomControl', 'typeSelector']
    });
    console.log(`Map initialized in ${containerId}`);
    return map;
}

function displayAnalysisData(routesData, maps) {
    const metricsBody = document.getElementById('metrics-body');
    metricsBody.innerHTML = '';

    // Соответствие ключей из ответа сервера и идентификаторов карт
    const algorithmMap = {
        'ant_colony': 'ant_colony',
        'genetic': 'genetic',
        'clarke_wright': 'clarke_wright',
        'gnn': 'gnn'
    };

    Object.entries(algorithmMap).forEach(([apiKey, mapKey]) => {
        const data = routesData[apiKey];
        
        if (!data || data.error || !data?.routes?.[0]?.points) {
            console.warn(`No valid route data for ${apiKey}`, data);
            // Добавляем строку с ошибкой в таблицу
            metricsBody.innerHTML += `
                <tr class="error-row">
                    <td>${getAlgorithmName(apiKey)}</td>
                    <td colspan="4">${data?.error || 'Нет данных о маршруте'}</td>
                </tr>
            `;
            return;
        }

        // Добавляем маршрут на карту
        const route = data.routes[0];
        const polyline = new ymaps.Polyline(route.points, {}, {
            strokeColor: getRouteColor(apiKey),
            strokeWidth: 5,
            strokeOpacity: 0.7
        });
        
        maps[mapKey].geoObjects.add(polyline);
        maps[mapKey].setBounds(polyline.geometry.getBounds());

        // Добавляем метрики в таблицу
        metricsBody.innerHTML += `
            <tr>
                <td>${getAlgorithmName(apiKey)}</td>
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
        'ant_colony': 'Муравьиный алгоритм',
        'genetic': 'Генетический алгоритм',
        'clarke_wright': 'Кларка-Райта'
    };
    return names[key] || key;
}

function getRouteColor(algorithm) {
    const colors = {
        'gnn': '#4CAF50',
        'ant_colony': '#FF5722',
        'genetic': '#2196F3',
        'clarke_wright': '#9C27B0'
    };
    return colors[algorithm] || '#000000';
}