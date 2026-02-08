const CPU_HISTORY = [];
const RAM_HISTORY = [];
const MAX_POINTS = 120;

let cpuChart = null;
let ramChart = null;

function initCharts() {
    const chartOpts = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            y: {
                min: 0, max: 100,
                grid: { color: '#2a2a4a' },
                ticks: { color: '#a0a0b0', font: { size: 10 } },
            },
            x: { display: false },
        },
        plugins: { legend: { display: false } },
        animation: { duration: 300 },
        elements: { point: { radius: 0 } },
    };

    const cpuCtx = document.getElementById('chart-cpu').getContext('2d');
    cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                data: [],
                borderColor: '#4ecca3',
                backgroundColor: 'rgba(78, 204, 163, 0.1)',
                fill: true,
                tension: 0.3,
                borderWidth: 2,
            }],
        },
        options: chartOpts,
    });

    const ramCtx = document.getElementById('chart-ram').getContext('2d');
    ramChart = new Chart(ramCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                data: [],
                borderColor: '#3498db',
                backgroundColor: 'rgba(52, 152, 219, 0.1)',
                fill: true,
                tension: 0.3,
                borderWidth: 2,
            }],
        },
        options: { ...chartOpts },
    });
}

function updateCharts(data) {
    if (!cpuChart) initCharts();

    CPU_HISTORY.push(data.cpu_percent);
    RAM_HISTORY.push(data.ram.percent);

    if (CPU_HISTORY.length > MAX_POINTS) CPU_HISTORY.shift();
    if (RAM_HISTORY.length > MAX_POINTS) RAM_HISTORY.shift();

    cpuChart.data.labels = CPU_HISTORY.map(() => '');
    cpuChart.data.datasets[0].data = [...CPU_HISTORY];
    cpuChart.update('none');

    ramChart.data.labels = RAM_HISTORY.map(() => '');
    ramChart.data.datasets[0].data = [...RAM_HISTORY];
    ramChart.update('none');
}
