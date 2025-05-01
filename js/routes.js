let routes = [];
let currentRouteIndex = -1;

async function optimizeRoutes() {
    if (containers.length === 0) {
        alert("Нет контейнеров для построения маршрута!");
        return;
    }

    const maxContainers = parseInt(document.getElementById("max-containers").value) || 20;

    if (maxContainers <= 0 || isNaN(maxContainers)) {
        alert("Пожалуйста, укажите корректную вместимость мусоровоза!");
        return;
    }

    try {
        const response = await fetch('http://localhost:5000/gnn-optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ containers, maxContainers })
        });

        const data = await response.json();

        if (data.error) {
            alert("Ошибка от сервера: " + data.error);
            return;
        }

        if (!data.routes || data.routes.length === 0) {
            alert("GNN не вернула ни одного маршрута.");
            return;
        }

        routes = data.routes.map((r, i) => {
            // собираем контейнеры, привязанные к узлам маршрута:
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
        console.error(err);
        alert("Ошибка при обращении к серверу GNN: " + err.message);
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

function showRoute(index) {
    if (!routes[index]) {
        alert("Выбранный маршрут не найден.");
        return;
    }

    currentRouteIndex = index;
    const route = routes[index];

    clearMap();

    const polyline = new ymaps.Polyline(route.routePoints, {}, {
        strokeColor: route.color,
        strokeWidth: 5,
        strokeOpacity: 0.8
    });
    map.geoObjects.add(polyline);

    route.containers.forEach(container => {
        addPlacemark(container);
    });

    updateContainerList(route.containers);
}

function getRouteColor(index) {
    const colors = ['#FF0000', '#00FF00', '#0000FF', '#FF00FF', '#FFA500', '#00CED1'];
    return colors[index % colors.length];
}
