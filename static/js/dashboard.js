// ==========================================================================
// AGRIBOT - Dashboard Data Binding
// --------------------------------------------------------------------------
// Fetches project metrics from the backend and renders role-specific dashboard
// interfaces without hardcoded demo values.
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
    setupUserDashboard();
    setupAdminDashboard();
});

async function setupUserDashboard() {
    const root = document.querySelector("[data-user-dashboard]");

    if (!root) {
        return;
    }

    const data = await fetchDashboardData("/api/dashboard/user-metrics");

    if (!data) {
        return;
    }

    root.querySelectorAll("[data-user-metric]").forEach((element) => {
        const key = element.dataset.userMetric;
        element.textContent = data[key] ?? 0;
    });
}

async function setupAdminDashboard() {
    const root = document.querySelector("[data-admin-dashboard]");

    if (!root) {
        return;
    }

    const data = await fetchDashboardData("/api/dashboard/admin-metrics");

    if (!data) {
        return;
    }

    const statElements = root.querySelectorAll("[data-admin-metric]");
    const values = Array.from(statElements, (element) => Number(data[element.dataset.adminMetric] ?? 0));
    const maxValue = Math.max(...values, 1);

    statElements.forEach((element) => {
        const value = Number(data[element.dataset.adminMetric] ?? 0);
        element.textContent = value;
        element.closest("[data-admin-stat-card]")?.style.setProperty("--bar", `${Math.max(14, (value / maxValue) * 100)}%`);
    });

    renderAdminChart(
        root.querySelector("[data-admin-chart]"),
        root.querySelector("[data-admin-chart-labels]"),
        data.activity_labels || [],
        data.activity_series || [],
        data.login_series || []
    );
}

async function fetchDashboardData(url) {
    try {
        const response = await fetch(url, {
            headers: { Accept: "application/json" }
        });

        if (response.status === 401) {
            window.location.href = "/login";
            return null;
        }

        if (response.status === 403) {
            window.location.href = "/user-dashboard";
            return null;
        }

        const result = await response.json();

        if (result.status !== "success") {
            return null;
        }

        return result.data;
    } catch (error) {
        console.error("Dashboard data fetch failed:", error);
        return null;
    }
}

function renderAdminChart(svg, labelsContainer, labels, activitySeries, loginSeries) {
    if (!svg || !labelsContainer) {
        return;
    }

    const width = 760;
    const height = 320;
    const baseline = height - 24;
    const maxValue = Math.max(...activitySeries, ...loginSeries, 1);

    labelsContainer.innerHTML = labels.map((label) => `<span>${label}</span>`).join("");

    const buildAreaPath = (series) => {
        if (!series.length) {
            return "";
        }

        const step = width / Math.max(series.length - 1, 1);
        const points = series.map((value, index) => {
            const x = index * step;
            const y = baseline - (value / maxValue) * 220;
            return { x, y };
        });

        const line = points.map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ");
        return `${line} L ${width},${baseline} L 0,${baseline} Z`;
    };

    const buildGrid = () => {
        const rows = 5;
        const lines = [];

        for (let index = 0; index < rows; index += 1) {
            const y = 30 + (index * 52);
            lines.push(`<line x1="0" y1="${y}" x2="${width}" y2="${y}"></line>`);
        }

        return lines.join("");
    };

    svg.innerHTML = `
        <defs>
            <linearGradient id="adminPrimaryArea" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="rgba(255,255,255,0.96)"></stop>
                <stop offset="100%" stop-color="rgba(255,255,255,0.14)"></stop>
            </linearGradient>
            <linearGradient id="adminSecondaryArea" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="rgba(173,235,255,0.72)"></stop>
                <stop offset="100%" stop-color="rgba(173,235,255,0.14)"></stop>
            </linearGradient>
        </defs>
        <g opacity="0.18" stroke="rgba(255,255,255,0.35)" stroke-width="1">
            ${buildGrid()}
        </g>
        <path fill="url(#adminSecondaryArea)" d="${buildAreaPath(activitySeries)}"></path>
        <path fill="url(#adminPrimaryArea)" d="${buildAreaPath(loginSeries)}"></path>
    `;
}
