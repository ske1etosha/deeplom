let map;

function initMap() {
    ymaps.ready(() => {
        map = new ymaps.Map("map", { 
            center: [51.8345, 107.5845], 
            zoom: 13, 
            controls: ['zoomControl', 'typeSelector', 'fullscreenControl'] 
        });

        map.events.add('click', e => addManualContainer(e.get('coords')));
    });
}
//=================================================================================//
function addPlacemark(container) {
    let color;
    if (container.fillLevel >= 80) {
        color = 'islands#redIcon';
    } else if (container.fillLevel >= 40) {
        color = 'islands#orangeIcon';
    } else {
        color = 'islands#greenIcon';
    }

    const placemark = new ymaps.Placemark([container.latitude, container.longitude], {
        balloonContent: `
            <div style="padding: 10px;">
                <h3 style="margin-top: 0;">${container.address}</h3>
                <p><strong>Координаты:</strong> ${container.latitude.toFixed(6)}, ${container.longitude.toFixed(6)}</p>
                <p><strong>Заполненность:</strong> <span class="${getFillClass(container.fillLevel)}">${container.fillLevel}%</span></p>
                <p><strong>Дата:</strong> ${new Date(container.timestamp).toLocaleString()}</p>
                <button onclick="removeContainer(${container.id})" 
                        style="background: #F44336; color: white; border: none; padding: 5px 10px; border-radius: 3px; cursor: pointer;">
                    Удалить
                </button>
            </div>
        `
    }, { preset: color });

    map.geoObjects.add(placemark);
    placemarks[container.id] = placemark;
}

function clearMap() {
    map.geoObjects.removeAll();
    placemarks = {};
    // if (currentRoute) {
    //     map.geoObjects.remove(currentRoute);
    //     currentRoute = null;
    // }
    // document.getElementById('route-info').innerHTML = 'Маршруты не построены';
}
//=================================================================================//
function addManualContainer(coords) {
    const fillLevel = prompt("Введите заполненность контейнера в % (0-100):");
    if (fillLevel === null || isNaN(fillLevel) || fillLevel < 0 || fillLevel > 100) {
        alert("Некорректный ввод. Введите число от 0 до 100.");
        return;
    }
    
    ymaps.geocode(coords).then(function(res) {
        const address = res.geoObjects.get(0)?.getAddressLine() || "Адрес не определен";
        const container = {
            id: Date.now(),
            address,
            latitude: coords[0],
            longitude: coords[1],
            timestamp: new Date().toISOString(),
            fillLevel: parseInt(fillLevel),
            source: "manual"
        };
        containers.push(container);
        addPlacemark(container);
        updateContainerList();
    });
}