let comparisonChart = null;
let efficiencyChart = null;

function initComparisonChart() {
    const ctx = document.getElementById('time-comparison-chart').getContext('2d');
    comparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Время выполнения', 'Общее время'],
            datasets: []
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Время (секунды)'
                    }
                }
            }
        }
    });
}

function initEfficiencyChart() {
    const ctx = document.getElementById('route-efficiency-chart').getContext('2d');
    efficiencyChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Длина маршрута', 'Контейнеры'],
            datasets: [{
                data: [0, 0],
                backgroundColor: [
                    '#4CAF50',
                    '#2196F3'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function updateCharts(routeData) {
    if (!routeData || !routeData.metrics) return;

    // Обновляем диаграмму сравнения
    if (comparisonChart) {
        comparisonChart.data.datasets = [{
            label: 'Текущий маршрут',
            data: [
                routeData.metrics.execution_time,
                routeData.metrics.estimated_time
            ],
            backgroundColor: [
                'rgba(255, 99, 132, 0.7)',
                'rgba(54, 162, 235, 0.7)'
            ]
        }];
        comparisonChart.update();
    }

    // Обновляем диаграмму эффективности
    if (efficiencyChart) {
        efficiencyChart.data.datasets[0].data = [
            routeData.metrics.distance / 1000, // км
            routeData.metrics.containers_served
        ];
        efficiencyChart.update();
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    initComparisonChart();
    initEfficiencyChart();
});