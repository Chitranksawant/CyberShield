window.onload = function() {
    // --- Theme ---
    const theme = localStorage.getItem("theme");
    if (theme === "dark") {
        document.body.classList.add("dark");
    } else {
        document.body.classList.remove("dark");
        if (!theme) localStorage.setItem("theme", "light");
    }

    // --- Preview Mode ---
    const previewCheckbox = document.getElementById("previewToggle");
    if (previewCheckbox) {
        const saved = localStorage.getItem("previewMode");
        previewCheckbox.checked = saved === "true";
    }

    // Initial load of comments if dashboard is visible
    if (document.getElementById("commentsTable")) {
        loadComments();
    }
};

// Sidebar toggle
function toggleSidebar() {
    document.getElementById("sidebar").classList.toggle("closed");
    document.getElementById("main-content").classList.toggle("full");
}

// Dark mode toggle
function toggleTheme() {
    document.body.classList.toggle("dark");
    localStorage.setItem("theme", document.body.classList.contains("dark") ? "dark" : "light");
}

// Load Comments (Dashboard)
async function loadComments() {
    const resp = await fetch("/get_comments");
    const data = await resp.json();
    const tableBody = document.querySelector("#commentsTable tbody");
    tableBody.innerHTML = "";

    if (data.comments) {
        data.comments.forEach(item => {
            const row = document.createElement("tr");

            // Comment cell
            const commentCell = document.createElement("td");
            commentCell.textContent = item.comment;
            row.appendChild(commentCell);

            // Toxicity cell
            const toxicityCell = document.createElement("td");
            toxicityCell.textContent = (item.toxicity !== undefined) ? item.toxicity.toFixed(2) + "%" : "N/A";
            row.appendChild(toxicityCell);

            // Status cell
            const statusCell = document.createElement("td");
            statusCell.textContent = item.status || "Safe";
            row.appendChild(statusCell);

            // Remove previous classes
            row.classList.remove("comment-safe", "comment-toxic", "comment-deleted");

            // Add class based on status
            if (item.status === "Deleted") {
                row.classList.add("comment-deleted");
                showNotification("🚨 Toxic comment deleted!");
            } else if (item.status === "Preview (Toxic)") {
                row.classList.add("comment-toxic");
                showNotification("⚠️ Toxic comment detected (Preview Mode)");
            } else {
                row.classList.add("comment-safe");
            }

            tableBody.appendChild(row);
        });
    }
}

// Refresh button with loading feedback
const refreshBtn = document.getElementById("refreshBtn");
if (refreshBtn) refreshBtn.addEventListener("click", async () => {
    refreshBtn.disabled = true;                    
    const originalText = refreshBtn.textContent;
    refreshBtn.textContent = "⏳ Loading...";       

    try {
        await loadComments();                       
    } finally {
        refreshBtn.disabled = false;               
        refreshBtn.textContent = originalText;     
    }
});

// Dashboard link auto-refresh (SPA friendly)
const dashboardLink = document.getElementById("dashboardLink");
if (dashboardLink) {
    dashboardLink.addEventListener("click", () => {
        // Optional: scroll to top
        document.getElementById("main-content").scrollTop = 0;
        loadComments();
    });
}

// Preview Mode Toggle
const previewToggle = document.getElementById("previewToggle");
if (previewToggle) {
    previewToggle.addEventListener("change", async (e) => {
        const enabled = e.target.checked;
        await fetch("/set_preview_mode", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ previewMode: enabled })
        });
        localStorage.setItem("previewMode", enabled);
        loadComments();
    });
}

// Notifications
let notificationTimeout;
function showNotification(message) {
    // Only show notification if enabled in settings
    if (localStorage.getItem("notificationsEnabled") !== "true") return;

    const notification = document.getElementById("notification");
    notification.textContent = message;
    notification.classList.add("show");
    setTimeout(() => notification.classList.remove("show"), 3000);
}