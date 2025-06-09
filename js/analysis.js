document.addEventListener('DOMContentLoaded', function() {
    if (typeof ymaps === 'undefined') {
        console.error('Yandex Maps API not loaded');
        return;
    }

    ymaps.ready(async function() {
        try {
            // Проверяем наличие сохраненных данных
            const savedData = localStorage.getItem('analysisRequestData');
            if (!savedData) {
                throw new Error('Данные анализа не найдены');
            }
            
            const { request, response } = JSON.parse(savedData);
            
            // Инициализация карт
            const maps = {
                gnn: initMap('gnn-map'),
                ant_colony: initMap('ant-map'),
                genetic: initMap('genetic-map'),
                clarke_wright: initMap('clarke-map')
            };
            
            // Отображение данных
            displayAnalysisData(response, maps);
            
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
    const container = document.querySelector('.algorithms-comparison');
    container.innerHTML = '';
    
    Object.entries(routesData).forEach(([algorithmKey, data]) => {
        if (!data || data.error || !data?.routes?.[0]?.points) return;
        
        const algorithmName = getAlgorithmName(algorithmKey);
        const metrics = data.metrics || {};
        
        // Форматирование времени
        const formatTime = (seconds) => {
            if (!seconds) return '0 сек';
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.round(seconds % 60);
            
            let result = '';
            if (hours > 0) result += `${hours} ч `;
            if (minutes > 0) result += `${minutes} мин `;
            if (secs > 0 && hours === 0) result += `${secs} сек`;
            return result.trim() || '0 сек';
        };
        
        // Создаем карточку алгоритма
        const card = document.createElement('div');
        card.className = 'algorithm-card';
        card.innerHTML = `
            <h3>${algorithmName}</h3>
            <div class="time-summary" onclick="this.nextElementSibling.classList.toggle('active')">
                🕒 Общее время: <span class="metric-value">${formatTime(metrics.estimated_time)}</span>
            </div>
            <div class="time-details">
                <div class="time-detail-row">
                    <span>Движение:</span>
                    <span class="metric-value">${formatTime(metrics.driving_time)}</span>
                </div>
                <div class="time-detail-row">
                    <span>Разгрузка:</span>
                    <span class="metric-value">${formatTime(metrics.unloading_time)}</span>
                </div>
                <div class="time-detail-row">
                    <span>Время алгоритма:</span>
                    <span class="metric-value">${metrics.execution_time?.toFixed(2) || '0'} сек</span>
                </div>
            </div>
            <div class="other-metrics">
                <div class="metric-item">
                    <span class="metric-label">Длина маршрута</span>
                    <span class="metric-value">${(metrics.distance / 1000).toFixed(2)} км</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Контейнеров</span>
                    <span class="metric-value">${metrics.containers_served || 0}</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Скорость</span>
                    <span class="metric-value">${metrics.avg_speed ? metrics.avg_speed.toFixed(1) : '?'} км/ч</span>
                </div>
                <div class="metric-item">
                    <span class="metric-label">Эффективность</span>
                    <span class="metric-value">${metrics.efficiency ? metrics.efficiency.toFixed(1) : '?'} конт/час</span>
                </div>
            </div>
        `;
        
        container.appendChild(card);
        
        // Добавляем маршрут на карту
        const route = data.routes[0];
        const polyline = new ymaps.Polyline(route.points, {}, {
            strokeColor: getRouteColor(algorithmKey),
            strokeWidth: 5,
            strokeOpacity: 0.7
        });
        
        maps[algorithmKey].geoObjects.add(polyline);
        maps[algorithmKey].setBounds(polyline.geometry.getBounds());
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

// Делаем функцию доступной глобально для обработки кликов
window.toggleTimeDetails = function(element) {
    element.nextElementSibling.classList.toggle('active');
};