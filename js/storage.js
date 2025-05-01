function saveToJSON() {
    if (containers.length === 0) return alert("Нет данных для сохранения!");
    
    const dataToSave = containers.map(c => ({
        id: c.id,
        address: c.address,
        latitude: c.latitude,
        longitude: c.longitude,
        timestamp: c.timestamp,
        source: c.source,
        fill_percentage: c.fillLevel
    }));
    
    const blob = new Blob([JSON.stringify(dataToSave, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `containers_${new Date().toISOString().slice(0,10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function loadFromJSON() {
    return new Promise((resolve) => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = "application/json";
        
        input.addEventListener("change", async (event) => {
            const file = event.target.files[0];
            if (!file) return resolve(null);

            try {
                const content = await file.text();
                const loadedData = JSON.parse(content);
                
                if (!Array.isArray(loadedData)) {
                    throw new Error("Файл должен содержать массив данных");
                }

                resolve(loadedData.map(c => ({
                    id: c.id || Date.now(),
                    address: c.address || "Адрес не указан",
                    latitude: c.latitude,
                    longitude: c.longitude,
                    timestamp: c.timestamp || new Date().toISOString(),
                    source: c.source || "manual",
                    fillLevel: c.fill_percentage !== undefined ? c.fill_percentage : c.fillLevel !== undefined ? c.fillLevel : 0
                })));
            } catch (error) {
                alert("Ошибка при загрузке файла: " + error.message);
                resolve(null);
            }
        });

        input.click();
    });
}