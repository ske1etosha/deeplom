let routes = [];
let currentRouteIndex = -1;

async function optimizeRoutes() {
    if (containers.length === 0) {
        alert("Нет контейнеров для построения маршрута!");
        return;
    }

    const maxContainers = parseInt(document.getElementById("max-containers").value) || 20;
    const algorithm = document.getElementById("algorithm-select").value;

    if (maxContainers <= 0 || isNaN(maxContainers)) {
        alert("Пожалуйста, укажите корректную вместимость мусоровоза!");
        return;
    }

    try {
        let endpoint;
        const baseUrl = 'http://localhost:5000'; // Базовый URL Flask сервера
        
        switch(algorithm) {
            case 'ant':
                console.log("Отправляемые данные:", {
                    containers: containers,
                    maxContainers: maxContainers
                  });
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
                containers: containers, 
                maxContainers: maxContainers 
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (!data.routes || data.routes.length === 0) {
            alert("Алгоритм не вернул ни одного маршрута.");
            return;
        }

        routes = data.routes.map((r, i) => {
            const containersForRoute = containers.filter(c =>
                r.nodes.includes(c.nearest_node)
            );
            return {
                index: i,
                containers: containersForRoute,
                routePoints: r.points,
                color: getRouteColor(i)
            };
        });

        console.log("Маршруты получены:", routes);
        clearMap();
        updateRouteSelector();
        showRoute(0);

    } catch (err) {
        console.error("Ошибка при оптимизации маршрута:", err);
        alert("Ошибка при оптимизации маршрута: " + err.message);
    }
}

function updateRouteSelector() {
    const routeInfo = document.getElementById('route-info');
    routeInfo.innerHTML = `
        <strong>Построено маршрутов:</strong> ${routes.length}
        <select id="route-selector" class="route-selector">
            ${routes.map((r, i) => `<option value="${i}">Маршрут ${i + 1} (${r.containers.length} контейнеров)</option>`).join('')}
        </select>
    `;
    document.getElementById('route-selector').addEventListener('change', (e) => {
        showRoute(parseInt(e.target.value));
    });
}

// function showRoute(index) {
//     if (!routes[index]) {
//         alert("Выбранный маршрут не найден.");
//         return;
//     }

//     currentRouteIndex = index;
//     const route = routes[index];

//     clearMap();

//     const polyline = new ymaps.Polyline(route.routePoints, {}, {
//         strokeColor: route.color,
//         strokeWidth: 5,
//         strokeOpacity: 0.8
//     });
//     map.geoObjects.add(polyline);

//     route.containers.forEach(container => {
//         addPlacemark(container);
//     });

//     updateContainerList(route.containers);
// }
function showRoute(index) {
    if (!routes[index]) {
        alert("Выбранный маршрут не найден.");
        return;
    }

    const route = routes[index];
    currentRouteIndex = index;
    clearMap();

    // Отрисовываем линию маршрута
    const polyline = new ymaps.Polyline(route.routePoints, {}, {
        strokeColor: route.color,
        strokeWidth: 5,
        strokeOpacity: 0.8
    });
    map.geoObjects.add(polyline);

    // Отрисовываем все контейнеры (без изменений стиля)
    containers.forEach(container => {
        addPlacemark(container);
    });

    updateContainerList(route.containers);
    
    // Центрируем карту на маршруте
    if (route.routePoints.length > 0) {
        map.setBounds(polyline.geometry.getBounds());
    }
}

function getRouteColor(index) {
    const colors = ['#FF0000', '#00FF00', '#0000FF', '#FF00FF', '#FFA500', '#00CED1'];
    return colors[index % colors.length];
}
