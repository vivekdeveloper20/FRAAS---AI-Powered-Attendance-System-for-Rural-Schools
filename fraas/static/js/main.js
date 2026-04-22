// Main Utilities
document.addEventListener("DOMContentLoaded", () => {
    // Update local clock
    const updateTime = () => {
        const now = new Date();
        const dateEl = document.getElementById("currentDate");
        const timeEl = document.getElementById("currentTime");
        
        if (dateEl) {
            dateEl.textContent = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
        }
        if (timeEl) {
            timeEl.textContent = now.toLocaleTimeString('en-US', { hour: '2-digit', minute:'2-digit' });
        }
    };
    
    updateTime();
    setInterval(updateTime, 1000);
});
