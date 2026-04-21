// ==========================================================================
// AGRIBOT - Shared Frontend Interactions
// --------------------------------------------------------------------------
// Lightweight interaction helpers keep the UI responsive while supporting
// the crop form, disease upload, chatbot flow, reveal animations, and mobile
// navigation without introducing a heavy framework.
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
    setupNavigation();
    setupLogout();
    setupRevealAnimations();
    setupCropPrediction();
    setupDiseaseUpload();
    setupChatbot();
});

function setupNavigation() {
    const toggle = document.querySelector("[data-nav-toggle]");
    const menu = document.querySelector("[data-nav-menu]");
    const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
    const sidebar = document.querySelector("[data-sidebar]");
    const sidebarOverlay = document.querySelector("[data-sidebar-overlay]");
    const sidebarClose = document.querySelector("[data-sidebar-close]");

    if (toggle && menu) {
        toggle.addEventListener("click", () => {
            menu.classList.toggle("is-open");
        });
    }

    if (!sidebarToggle || !sidebar || !sidebarOverlay) {
        return;
    }

    const openSidebar = () => {
        document.body.classList.add("sidebar-open");
    };

    const closeSidebar = () => {
        document.body.classList.remove("sidebar-open");
    };

    sidebarToggle.addEventListener("click", openSidebar);
    sidebarOverlay.addEventListener("click", closeSidebar);
    sidebarClose?.addEventListener("click", closeSidebar);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeSidebar();
        }
    });

    sidebar.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", closeSidebar);
    });
}

function setupLogout() {
    const logoutButton = document.querySelector("[data-logout-button]");

    if (!logoutButton) {
        return;
    }

    logoutButton.addEventListener("click", async () => {
        try {
            await fetch("/logout", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
        } catch (error) {
            console.error("Logout request failed:", error);
        } finally {
            window.location.href = "/login";
        }
    });
}

function setupRevealAnimations() {
    const revealItems = document.querySelectorAll("[data-reveal]");

    if (!revealItems.length) {
        return;
    }

    const observer = new IntersectionObserver((entries, currentObserver) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) {
                return;
            }

            entry.target.classList.add("is-visible");
            currentObserver.unobserve(entry.target);
        });
    }, { threshold: 0.18 });

    revealItems.forEach((item) => observer.observe(item));
}

function setStatus(targetId, type, message) {
    const banner = document.getElementById(targetId);

    if (!banner) {
        return;
    }

    banner.className = "status-banner visible";
    banner.classList.add(type);
    banner.textContent = message;
}

function clearStatus(targetId) {
    const banner = document.getElementById(targetId);

    if (!banner) {
        return;
    }

    banner.className = "status-banner";
    banner.textContent = "";
}

function renderResultCard(title, description, badgeText) {
    const resultBox = document.getElementById("result");

    if (!resultBox) {
        return;
    }

    resultBox.innerHTML = `
        <p class="eyebrow">${badgeText}</p>
        <h3>${title}</h3>
        ${description ? `<p>${description}</p>` : ""}
    `;
}

function setupCropPrediction() {
    const form = document.getElementById("cropForm");

    if (!form) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearStatus("cropStatus");
        setStatus("cropStatus", "info", "Running crop prediction...");

        const formData = new FormData(form);
        const payload = {
            N: parseFloat(formData.get("N")),
            P: parseFloat(formData.get("P")),
            K: parseFloat(formData.get("K")),
            temperature: parseFloat(formData.get("temperature")),
            humidity: parseFloat(formData.get("humidity")),
            ph: parseFloat(formData.get("ph")),
            rainfall: parseFloat(formData.get("rainfall"))
        };

        try {
            const response = await fetch("/predict_crop", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const result = await parseJsonResponse(response);

            if (result.status === "success" && result.data) {
                renderResultCard(
                    `Recommended Crop: ${result.data}`,
                    "",
                    "Prediction Complete"
                );
                setStatus("cropStatus", "success", result.message || "Crop predicted successfully.");
                return;
            }

            renderResultCard(
                "Unable to generate a crop recommendation",
                result.message || "",
                "Prediction issue"
            );
            setStatus("cropStatus", "error", result.message || "Prediction failed.");
        } catch (error) {
            console.error("Crop prediction failed:", error);
            renderResultCard(
                "Server connection issue",
                "",
                "Connection error"
            );
            setStatus("cropStatus", "error", "Server error. Please try again.");
        }
    });

    form.addEventListener("reset", () => {
        clearStatus("cropStatus");
            renderResultCard(
                "Prediction",
                "Submit the form to view the crop recommendation.",
                "Prediction Complete"
            );
    });
}

function setupDiseaseUpload() {
    const form = document.getElementById("uploadForm");
    const fileInput = document.getElementById("plant-image");
    const plantSelect = document.getElementById("plant-name");
    const previewBox = document.getElementById("imagePreview");
    let activePreviewUrl = "";

    if (!form || !fileInput || !plantSelect || !previewBox) {
        return;
    }

    fileInput.addEventListener("change", () => {
        const [file] = fileInput.files || [];

        if (!file) {
            if (activePreviewUrl) {
                URL.revokeObjectURL(activePreviewUrl);
                activePreviewUrl = "";
            }
            previewBox.innerHTML = "<p class=\"muted-copy\">Image preview will appear here.</p>";
            return;
        }

        if (activePreviewUrl) {
            URL.revokeObjectURL(activePreviewUrl);
        }

        activePreviewUrl = URL.createObjectURL(file);
        previewBox.innerHTML = `<img src="${activePreviewUrl}" alt="Selected plant preview">`;
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearStatus("uploadStatus");

        const formData = new FormData(form);
        if (!formData.get("plant_name")) {
            setStatus("uploadStatus", "error", "Please select the plant before detecting the disease.");
            return;
        }

        if (!formData.get("file") || !fileInput.files.length) {
            setStatus("uploadStatus", "error", "Please choose an image before submitting.");
            return;
        }

        setStatus("uploadStatus", "info", "Uploading image and running disease detection...");

        try {
            const response = await fetch("/predict_disease", {
                method: "POST",
                body: formData
            });

            const result = await parseJsonResponse(response);

            if (result.status === "success") {
                const resultDescription = result.message && result.message !== "Disease detected."
                    ? result.message
                    : "";

                renderResultCard(
                    result.data || "Disease detected",
                    resultDescription,
                    "Detected Disease"
                );
                setStatus("uploadStatus", "success", result.message || "Disease detection completed.");
                return;
            }

            const diagnosisTitle = result.message && result.message.includes("not supported")
                ? "Plant not supported"
                : "Diagnosis unavailable";

            renderResultCard(
                diagnosisTitle,
                result.message || "",
                "Detection issue"
            );
            setStatus("uploadStatus", "error", result.message || "Disease detection failed.");
        } catch (error) {
            console.error("Disease prediction failed:", error);
            renderResultCard(
                "Server connection issue",
                "",
                "Connection error"
            );
            setStatus("uploadStatus", "error", "Server error. Please try again.");
        }
    });

    form.addEventListener("reset", () => {
        clearStatus("uploadStatus");
        if (activePreviewUrl) {
            URL.revokeObjectURL(activePreviewUrl);
            activePreviewUrl = "";
        }
        previewBox.innerHTML = "<p class=\"muted-copy\">Image preview will appear here.</p>";
        renderResultCard(
            "Select the plant and upload an image to detect the disease.",
            "",
            "Detected Disease"
        );
    });
}

function setupChatbot() {
    const form = document.getElementById("chatbotForm");
    const input = document.getElementById("userInput");
    const chatLog = document.getElementById("chatLog");

    if (!form || !input || !chatLog) {
        return;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearStatus("chatStatus");

        const message = input.value.trim();
        if (!message) {
            setStatus("chatStatus", "error", "Please type a question before sending.");
            return;
        }

        appendChatBubble(chatLog, message, "user");
        form.reset();
        setStatus("chatStatus", "info", "Agribot is preparing a reply...");

        try {
            const response = await fetch("/chatbot", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message })
            });

            const result = await parseJsonResponse(response);
            const reply = result.data || result.message || "No response received.";

            appendChatBubble(chatLog, reply, "bot");

            if (result.status === "success") {
                setStatus("chatStatus", "success", "Response received.");
            } else {
                setStatus("chatStatus", "error", result.message || "Chatbot request failed.");
            }
        } catch (error) {
            console.error("Chatbot request failed:", error);
            appendChatBubble(chatLog, "Try again.", "bot");
            setStatus("chatStatus", "error", "Server error. Please try again.");
        }
    });

    form.addEventListener("reset", () => {
        clearStatus("chatStatus");
    });
}

function appendChatBubble(log, message, type) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${type}`;
    bubble.textContent = message;
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
}

async function parseJsonResponse(response) {
    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Authentication required.");
    }

    return response.json();
}
