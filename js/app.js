let containers = [];
let placemarks = {};
let currentRoute = null;

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    initMap();
    setupEventListeners();
}

function setupEventListeners() {
    document.getElementById('menu-toggle').addEventListener('click', toggleMenu);
    document.getElementById('menu-overlay').addEventListener('click', toggleMenu);
    document.getElementById('save-btn').addEventListener('click', saveToJSON);
    document.getElementById('load-btn').addEventListener('click', handleLoad);
    document.getElementById('clear-btn').addEventListener('click', clearAll);
    document.getElementById('optimize-btn').addEventListener('click', optimizeRoutes);
}

function toggleMenu() {
    document.body.classList.toggle('menu-open');
}

async function handleLoad() {
    const loadedData = await loadFromJSON();
    if (loadedData) {
        containers = loadedData;
        updateContainerList();
        clearMap();
        containers.forEach(container => addPlacemark(container));
    }
}

function clearAll() {
    if (confirm("Вы действительно хотите удалить все данные?")) {
        containers = [];
        routes = [];
        currentRouteIndex = -1;
        updateContainerList();
        clearMap();
        document.getElementById('route-info').innerHTML = 'Маршруты не построены';
    }
}

function updateContainerList(containersToShow = containers) {
    const list = document.getElementById('container-list');
    document.getElementById('counter').textContent = containersToShow.length;
    
    if (containersToShow.length === 0) {
        list.innerHTML = '<div class="no-data">Нет данных</div>';
        return;
    }
    
    list.innerHTML = '';
    containersToShow.forEach(container => {
        const item = document.createElement('div');
        item.className = 'container-item';
        item.innerHTML = `
            <div class="container-address">${container.address}</div>
            <div class="container-coords">${container.latitude.toFixed(6)}, ${container.longitude.toFixed(6)}</div>
            <span class="container-fill ${getFillClass(container.fillLevel)}">
                ${container.fillLevel}% заполнено
            </span>
            <button class="delete-btn" onclick="removeContainer(${container.id})" title="Удалить">
                <i class="fas fa-times"></i>
            </button>
        `;
        list.appendChild(item);
    });
}

function getFillClass(percentage) {
    if (percentage >= 80) return 'fill-high';
    if (percentage >= 40) return 'fill-medium';
    return 'fill-low';
}

function removeContainer(id) {
    if (confirm("Вы действительно хотите удалить этот контейнер?")) {
        containers = containers.filter(c => c.id !== id);
        updateContainerList();
        if (placemarks[id]) {
            map.geoObjects.remove(placemarks[id]);
            delete placemarks[id];
        }
    }
}

// Глобальные функции для вызова из HTML
window.removeContainer = removeContainer;