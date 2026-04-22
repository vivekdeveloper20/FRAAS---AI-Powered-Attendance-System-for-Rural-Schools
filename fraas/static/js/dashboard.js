document.addEventListener('DOMContentLoaded', () => {
    // Globals for Charts so we can update them on polling
    let attendanceChartInstance = null;
    let classwiseChartInstance = null;

    // Chart.js Default styling
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = '#6b7280';

    function initAttendanceChart(labels, dataArr) {
        const chartCanvas = document.getElementById('attendanceChart');
        if (!chartCanvas) return;
        
        const ctx = chartCanvas.getContext('2d');
        let gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(79, 70, 229, 0.4)'); // primary soft
        gradient.addColorStop(1, 'rgba(79, 70, 229, 0.0)');
        
        attendanceChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Present Students',
                    data: dataArr, 
                    borderColor: '#4F46E5',
                    backgroundColor: gradient,
                    borderWidth: 3,
                    pointBackgroundColor: '#fff',
                    pointBorderColor: '#4F46E5',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1F2937',
                        padding: 12,
                        titleFont: { size: 13 },
                        bodyFont: { size: 14, weight: 'bold' },
                        displayColors: false,
                        cornerRadius: 8,
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: '#f3f4f6', drawBorder: false },
                        ticks: { padding: 10, precision: 0 }
                    },
                    x: {
                        grid: { display: false, drawBorder: false },
                        ticks: { padding: 10 }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                animation: { duration: 500 }
            }
        });
    }

    function initClasswiseChart(labels, dataArr) {
        const chartCanvas = document.getElementById('classwiseChart');
        if (!chartCanvas) return;
        
        const ctx = chartCanvas.getContext('2d');
        
        classwiseChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: dataArr,
                    backgroundColor: [
                        '#4F46E5', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#3B82F6', '#EC4899'
                    ],
                    borderWidth: 2,
                    borderColor: '#ffffff',
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { 
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 20 }
                    },
                    tooltip: {
                        backgroundColor: '#1F2937',
                        padding: 10,
                        callbacks: {
                            label: function(context) {
                                return ` ${context.label}: ${context.raw}%`;
                            }
                        }
                    }
                },
                animation: { duration: 500 }
            }
        });
    }

    // Real-Time Telemetry Fetcher
    const logsContainer = document.getElementById('activityLogs');
    let chartsInitialized = false;
    
    function updateDashboard() {
        fetch('/api/dashboard/stats')
        .then(res => res.json())
        .then(data => {
            // Update Numerical Cards
            const e1 = document.getElementById('dashTotalStudents'); if(e1) e1.innerText = data.total_students || 0;
            const e2 = document.getElementById('dashPresentToday'); if(e2) e2.innerText = data.present_today || 0;
            const e3 = document.getElementById('dashAbsentToday'); if(e3) e3.innerText = data.absent_today || 0;
            const e4 = document.getElementById('dashAccuracy'); if(e4) e4.innerText = (data.accuracy || 0) + "%";
            
            // Build HTML Strings for recent logs payload
            if(logsContainer && data.recent_logs) {
                let freshHtml = '';
                data.recent_logs.forEach(log => {
                    let iconHtml, cssClass;
                    if(log.status === 'known') {
                        iconHtml = '<i class="fa-solid fa-check"></i>';
                        cssClass = 'success';
                    } else {
                        iconHtml = '<i class="fa-solid fa-triangle-exclamation"></i>';
                        cssClass = 'warning';
                    }
                    
                    freshHtml += `
                        <div class="log-item">
                            <div class="log-icon ${cssClass}">${iconHtml}</div>
                            <div class="log-content">
                                <p class="log-title"><strong>${log.name}</strong> ${log.msg}</p>
                                <p class="log-time">${log.time_str}</p>
                            </div>
                        </div>
                    `;
                });
                
                if (freshHtml !== logsContainer.innerHTML) {
                    logsContainer.innerHTML = freshHtml || '<div class="p-3 text-center text-muted small">No logs yet</div>';
                }
            }

            // Update Charts
            if (!chartsInitialized) {
                initAttendanceChart(data.monthly_labels, data.monthly_data);
                initClasswiseChart(data.class_labels, data.class_data);
                chartsInitialized = true;
            } else {
                if(attendanceChartInstance) {
                    attendanceChartInstance.data.labels = data.monthly_labels;
                    attendanceChartInstance.data.datasets[0].data = data.monthly_data;
                    attendanceChartInstance.update();
                }
                if(classwiseChartInstance) {
                    classwiseChartInstance.data.labels = data.class_labels;
                    classwiseChartInstance.data.datasets[0].data = data.class_data;
                    classwiseChartInstance.update();
                }
            }
        }).catch(err => {
            console.error("Dashboard Sync Error:", err);
        });
    }

    // Ping API every 2.5s sequentially
    setInterval(updateDashboard, 2500);
    updateDashboard(); // execute immediately
});
