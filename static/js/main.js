// ============================================================================
// AGRIBOT - Main JavaScript (clean rebuild)
// ============================================================================

document.addEventListener("DOMContentLoaded", () => {

    // Each module starts independently, so one failure can no longer
    // stop the others (menu, weather, crop form, chatbot...).
    const initializers = [
        setupNavigation,
        setupWeather,
        setupLogout,
        setupRevealAnimations,
        setupCropPrediction,
        setupDiseaseUpload,
        setupChatbot
    ];

    initializers.forEach((init) => {
        try {
            init();
        } catch (error) {
            console.error(`Agribot: ${init.name}() failed`, error);
        }
    });
});


// ============================================================================
// NAVIGATION + SIDEBAR (hamburger)
// ============================================================================

function setupNavigation() {

    const toggle = document.querySelector("[data-nav-toggle]");
    const menu = document.querySelector("[data-nav-menu]");
    const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
    const sidebar = document.querySelector("[data-sidebar]");
    const sidebarOverlay = document.querySelector("[data-sidebar-overlay]");
    const sidebarClose = document.querySelector("[data-sidebar-close]");

    if (toggle && menu) {
        toggle.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            menu.classList.toggle("is-open");
        });
    }

    if (!sidebarToggle || !sidebar) {
        console.warn("Agribot: sidebar elements not found", { sidebarToggle, sidebar });
        return;
    }

    function openSidebar() {
        document.body.classList.add("sidebar-open");
        if (sidebarOverlay) sidebarOverlay.classList.add("active");
        sidebar.setAttribute("aria-hidden", "false");
    }

    function closeSidebar() {
        document.body.classList.remove("sidebar-open");
        if (sidebarOverlay) sidebarOverlay.classList.remove("active");
        sidebar.setAttribute("aria-hidden", "true");
    }

    sidebarToggle.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (document.body.classList.contains("sidebar-open")) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    if (sidebarOverlay) sidebarOverlay.addEventListener("click", closeSidebar);
    if (sidebarClose) sidebarClose.addEventListener("click", closeSidebar);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeSidebar();
    });

    sidebar.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", closeSidebar);
    });

    sidebar.setAttribute("aria-hidden", "true");
}


// ============================================================================
// LOGOUT
// ============================================================================

function setupLogout() {

    const logoutButton = document.querySelector("[data-logout-button]");
    if (!logoutButton) return;

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


// ============================================================================
// REVEAL ANIMATIONS
// ============================================================================

function setupRevealAnimations() {

    const revealItems = document.querySelectorAll("[data-reveal]");
    if (!revealItems.length) return;

    if (!("IntersectionObserver" in window)) {
        revealItems.forEach((item) => item.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver((entries, currentObserver) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("is-visible");
            currentObserver.unobserve(entry.target);
        });
    }, { threshold: 0.15 });

    revealItems.forEach((item) => observer.observe(item));
}


// ============================================================================
// SHARED HELPERS
// ============================================================================

function setStatus(targetId, type, message) {
    const banner = document.getElementById(targetId);
    if (!banner) return;
    banner.className = "status-banner visible";
    banner.classList.add(type);
    banner.textContent = message;
}

function clearStatus(targetId) {
    const banner = document.getElementById(targetId);
    if (!banner) return;
    banner.className = "status-banner";
    banner.textContent = "";
}

async function parseJsonResponse(response) {

    if (response.status === 401) {
        window.location.href = "/login";
        throw new Error("Authentication required.");
    }

    let data;
    try {
        data = await response.json();
    } catch (error) {
        throw new Error("Server returned an invalid response.");
    }

    if (!response.ok) {
        throw new Error(data.message || `Request failed with status ${response.status}.`);
    }

    return data;
}

function renderResultCard(title, description, badgeText) {
    const resultBox = document.getElementById("result");
    if (!resultBox) return;

    resultBox.innerHTML = `
        <div class="crop-empty-state">
            <p class="eyebrow">${badgeText || "AI Analysis"}</p>
            <h3>${title}</h3>
            <p>${description || ""}</p>
        </div>
    `;
}


// ============================================================================
// CROP PREDICTION
// ============================================================================

function setupCropPrediction() {

    const form = document.getElementById("cropForm");
    if (!form) return;

    const resultBox = document.getElementById("result");
    let currentSpeechText = "";

    function resetListenButton() {
        const button = document.getElementById("cropListenBtn");
        if (button) {
            button.innerHTML = "🔊 Listen";
            button.classList.remove("speaking");
        }
    }

    function stopSpeech() {
        if ("speechSynthesis" in window) window.speechSynthesis.cancel();
        resetListenButton();
    }

    function speakExplanation() {

        if (!("speechSynthesis" in window)) {
            setStatus("cropStatus", "error", "Voice playback is not supported by this browser.");
            return;
        }
        if (!currentSpeechText) return;

        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(currentSpeechText);
        utterance.lang = "en-IN";
        utterance.rate = 0.9;
        utterance.pitch = 1;
        utterance.volume = 1;

        const indianVoice = window.speechSynthesis.getVoices().find(
            (voice) => voice.lang && voice.lang.toLowerCase() === "en-in"
        );
        if (indianVoice) utterance.voice = indianVoice;

        utterance.onstart = () => {
            const button = document.getElementById("cropListenBtn");
            if (button) {
                button.innerHTML = "🔊 Speaking...";
                button.classList.add("speaking");
            }
        };
        utterance.onend = resetListenButton;
        utterance.onerror = (error) => {
            console.error("Speech synthesis error:", error);
            resetListenButton();
        };

        window.speechSynthesis.speak(utterance);
    }

    function bindVoiceButtons() {
        const listenButton = document.getElementById("cropListenBtn");
        const stopButton = document.getElementById("cropStopBtn");
        if (listenButton) listenButton.addEventListener("click", speakExplanation);
        if (stopButton) stopButton.addEventListener("click", stopSpeech);
    }

    const voiceControlsHtml = `
        <div class="crop-voice-controls">
            <button type="button" id="cropListenBtn" class="crop-listen-btn">🔊 Listen</button>
            <button type="button" id="cropStopBtn" class="crop-stop-btn">⏹ Stop</button>
        </div>
    `;

    function formatCropName(cropName) {
        if (!cropName) return "Unknown Crop";
        return String(cropName).toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
    }

    function getConfidenceInfo(probability) {
        if (probability >= 70) return { label: "Excellent Match", className: "excellent" };
        if (probability >= 20) return { label: "Good Match", className: "good" };
        if (probability >= 5) return { label: "Moderate Match", className: "moderate" };
        if (probability >= 1) return { label: "Low Confidence", className: "low" };
        return { label: "Very Low Confidence", className: "very-low" };
    }

    function createCropCard(item, index) {

        const cropName = formatCropName(item.crop);
        const probability = Number(item.probability) || 0;
        const safeProbability = Math.max(0, Math.min(100, probability));
        const confidence = getConfidenceInfo(probability);
        const medals = ["🥇", "🥈", "🥉"];
        const rankText = index === 0 ? "Top Recommendation" : `Rank ${index + 1}`;

        return `
            <div class="crop-recommendation-card ${index === 0 ? "top-crop" : ""}">

                <div class="crop-rank">
                    <span class="crop-medal">${medals[index] || "🌱"}</span>
                    <span class="crop-rank-text">${rankText}</span>
                </div>

                <div class="crop-main-info">
                    <div class="crop-name-section">
                        <h4>${cropName}</h4>
                        <span class="crop-confidence-badge ${confidence.className}">
                            ${confidence.label}
                        </span>
                    </div>
                    <div class="crop-score">
                        <strong>${probability.toFixed(2)}%</strong>
                        <span>Model Confidence</span>
                    </div>
                </div>

                <div class="crop-progress-container">
                    <div class="crop-progress-track">
                        <div class="crop-progress-fill ${confidence.className}"
                             style="width: ${safeProbability}%;"></div>
                    </div>
                </div>

                ${index === 0 ? `
                    <div class="crop-primary-explanation">
                        <div class="explanation-title">🌱 Top Recommendation</div>
                        <p>
                            <strong>${cropName}</strong>
                            is the highest-ranked crop for the conditions you provided.
                        </p>
                    </div>
                ` : ""}

            </div>
        `;
    }

    form.addEventListener("submit", async (event) => {

        event.preventDefault();

        stopSpeech();
        currentSpeechText = "";
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

        if (Object.values(payload).some((value) => Number.isNaN(value))) {
            setStatus("cropStatus", "error",
                "Please enter valid numerical values for all crop parameters.");
            return;
        }

        try {

            const response = await fetch("/predict_crop", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const result = await parseJsonResponse(response);

            // ---------------- TOP 3 RESPONSE ----------------
            if (result.status === "success" &&
                Array.isArray(result.data) && result.data.length > 0) {

                const crops = result.data.slice(0, 3);
                const cropCards = crops.map((item, index) => createCropCard(item, index)).join("");

                const describe = (item) => ({
                    name: item ? formatCropName(item.crop) : "not available",
                    pct: item ? (Number(item.probability) || 0).toFixed(2) : "0.00"
                });

                const first = describe(crops[0]);
                const second = describe(crops[1]);
                const third = describe(crops[2]);

                if (resultBox) {
                    resultBox.innerHTML = `
                        <div class="crop-result-header">
                            <div>
                                <p class="eyebrow">Prediction Complete</p>
                                <h3>🌱 Crop Recommendations</h3>
                                <p class="crop-result-subtitle">
                                    Top crops based on your soil and environmental conditions.
                                </p>
                            </div>
                            <div class="ai-status-badge">
                                <span class="ai-status-dot"></span>
                                Analysis Complete
                            </div>
                        </div>

                        <div class="crop-recommendations-section">
                            <div class="section-heading">
                                <div>
                                    <h4>Top 3 Recommended Crops</h4>
                                    <p>Ranked according to the model's predicted probabilities.</p>
                                </div>
                            </div>
                            <div class="crop-recommendations-list">${cropCards}</div>
                        </div>

                        ${voiceControlsHtml}
                    `;

                    currentSpeechText =
                        `Agribot has completed the crop recommendation analysis. ` +
                        `The top recommended crop is ${first.name}, with a model confidence of ${first.pct} percent. ` +
                        `The second recommendation is ${second.name}, with a model confidence of ${second.pct} percent. ` +
                        `The third recommendation is ${third.name}, with a model confidence of ${third.pct} percent. ` +
                        `The prediction is based on nitrogen, phosphorus, potassium, temperature, humidity, soil pH and rainfall.`;

                    bindVoiceButtons();
                }

                setStatus("cropStatus", "success",
                    result.message || "Top 3 crop recommendations generated successfully.");
                return;
            }

            // ---------------- SINGLE CROP RESPONSE ----------------
            if (result.status === "success" && result.data && !Array.isArray(result.data)) {

                const cropData = result.data;
                const crop = formatCropName(cropData.crop || cropData);
                const explanation = cropData.explanation ||
                    "The crop has been recommended based on the provided soil and environmental conditions.";

                currentSpeechText = cropData.speech_text || explanation;

                if (resultBox) {
                    resultBox.innerHTML = `
                        <div class="crop-result-header">
                            <div>
                                <p class="eyebrow">Prediction Complete</p>
                                <h3>🌾 ${crop}</h3>
                                <p class="crop-result-subtitle">
                                    Recommended crop based on your conditions.
                                </p>
                            </div>
                        </div>

                        <div class="crop-primary-explanation">
                            <div class="explanation-title">🌱 Recommendation</div>
                            <p>${explanation}</p>
                        </div>

                        ${voiceControlsHtml}
                    `;
                    bindVoiceButtons();
                }

                setStatus("cropStatus", "success",
                    result.message || "Crop predicted successfully.");
                return;
            }

            throw new Error(result.message || "Crop prediction failed.");

        } catch (error) {

            console.error("Crop prediction failed:", error);
            renderResultCard(
                "Prediction Error",
                "Unable to complete crop prediction. Please try again.",
                "Error"
            );
            setStatus("cropStatus", "error", error.message || "Server error. Please try again.");
        }
    });

    form.addEventListener("reset", () => {
        stopSpeech();
        currentSpeechText = "";
        clearStatus("cropStatus");
        renderResultCard(
            "Your Recommendations",
            "Enter your soil and environmental conditions and click Predict Crops.",
            "AI Crop Analysis"
        );
    });
}


// ============================================================================
// DISEASE UPLOAD (leaf scan)
// ============================================================================

function setupDiseaseUpload() {

    const form = document.getElementById("uploadForm");
    if (!form) return;

    const plantSelect = document.getElementById("plant-name");
    const fileInput = document.getElementById("plant-image");
    const previewBox = document.getElementById("imagePreview");
    const submitButton = form.querySelector("button[type='submit']");

    const modal = document.getElementById("diseaseModal");
    const closeModalButton = document.getElementById("closeModalBtn");
    const modalBadge = document.getElementById("modalBadge");
    const modalTitle = document.getElementById("modalTitle");
    const modalDescription = document.getElementById("modalDescription");
    const modalMeta = document.getElementById("modalMeta");
    const causesSection = document.getElementById("modalCausesSection");
    const causesBox = document.getElementById("modalCauses");
    const solutionsSection = document.getElementById("modalSolutionsSection");
    const solutionsTitle = document.getElementById("modalSolutionsTitle");
    const solutionsBox = document.getElementById("modalSolutions");
    const modalActions = document.getElementById("modalActions");

    const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
    const PREVIEW_PLACEHOLDER = '<p class="muted-copy">Preview</p>';

    let activePreviewUrl = "";
    let busy = false;

    // ------------------------------------------------------------------
    // Small DOM helper (uses textContent, so server text can never inject HTML)
    // ------------------------------------------------------------------
    function make(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text != null) element.textContent = text;
        return element;
    }

    // ------------------------------------------------------------------
    // Image preview + client-side checks
    // ------------------------------------------------------------------
    function resetPreview() {
        if (activePreviewUrl) {
            URL.revokeObjectURL(activePreviewUrl);
            activePreviewUrl = "";
        }
        previewBox.innerHTML = PREVIEW_PLACEHOLDER;
    }

    function showPreview(file) {
        if (activePreviewUrl) URL.revokeObjectURL(activePreviewUrl);
        activePreviewUrl = URL.createObjectURL(file);

        const img = document.createElement("img");
        img.src = activePreviewUrl;
        img.alt = "Selected leaf image";

        previewBox.replaceChildren(img);
    }

    function rejectFile(message) {
        fileInput.value = "";
        resetPreview();
        setStatus("uploadStatus", "error", message);
    }

    fileInput.addEventListener("change", () => {

        clearStatus("uploadStatus");

        const file = fileInput.files[0];

        if (!file) {
            resetPreview();
            return;
        }

        if (/\.(heic|heif)$/i.test(file.name) || /hei[cf]/i.test(file.type)) {
            rejectFile("HEIC photos aren't supported. Please export the photo as JPG or PNG and try again.");
            return;
        }

        if (!file.type.startsWith("image/")) {
            rejectFile("Please choose an image file (JPG, PNG or WebP).");
            return;
        }

        if (file.size > MAX_UPLOAD_BYTES) {
            rejectFile(`That image is ${(file.size / 1024 / 1024).toFixed(1)} MB. Please choose one under 10 MB.`);
            return;
        }

        showPreview(file);
    });

    // ------------------------------------------------------------------
    // Modal open / close
    // ------------------------------------------------------------------
    function openModal() {
        if (!modal) return;
        modal.classList.add("active");
        document.body.style.overflow = "hidden";
        if (closeModalButton) closeModalButton.focus();
    }

    function closeModal() {
        if (!modal) return;
        modal.classList.remove("active");
        document.body.style.overflow = "";
    }

    if (closeModalButton) closeModalButton.addEventListener("click", closeModal);

    if (modal) {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) closeModal();
        });
    }

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && modal && modal.classList.contains("active")) {
            closeModal();
        }
    });

    // ------------------------------------------------------------------
    // Treatment advice from the Agribot chatbot (on demand)
    // ------------------------------------------------------------------
    async function loadAdvice(plantName, diseaseName, button, target) {

        button.disabled = true;
        button.textContent = "Asking Agribot...";

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 90000);

        try {

            const response = await fetch("/chatbot", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message:
                        `My ${plantName} plant has been diagnosed with ${diseaseName}. ` +
                        "What causes it, and how can I treat and prevent it? " +
                        "Keep the answer short and practical."
                }),
                signal: controller.signal
            });

            const result = await parseJsonResponse(response);

            let reply = result.data;

            if (reply && typeof reply === "object") {
                reply = reply.response || reply.message || reply.answer || reply.reply || "";
            }

            if (!reply) throw new Error("Empty answer");

            target.replaceChildren(make("p", "advice-text", String(reply)));
            button.remove();

        } catch (error) {

            console.error("Treatment advice failed:", error);
            target.replaceChildren(make("p", "advice-text",
                "Agribot couldn't load advice right now. Please try again in a moment."));
            button.disabled = false;
            button.textContent = "Try again";

        } finally {
            clearTimeout(timer);
        }
    }

    // ------------------------------------------------------------------
    // Render the diagnosis in the modal
    // ------------------------------------------------------------------
    function confidenceClass(percent) {
        if (percent >= 85) return "excellent";
        if (percent >= 60) return "good";
        if (percent >= 40) return "moderate";
        return "low";
    }

    function renderTreatment(container, sections) {
        sections.forEach((section) => {
            if (!section.items || !section.items.length) return;
            container.appendChild(make("h4", "", section.title));
            const list = make("ul");
            section.items.forEach((item) => list.appendChild(make("li", "", item)));
            container.appendChild(list);
        });
    }

    function renderDiagnosis(result) {

        const data = result.data || {};
        const type = data.result_type || "disease";
        const diagnosed = type === "disease" || type === "healthy" || type === "online";
        const percent = Number(data.confidence);

        const badges = {
            disease: "Detected Disease",
            healthy: "Healthy Plant",
            online: data.is_healthy ? "Healthy Plant (online check)" : "Online Model Result",
            uncertain: "Not Sure Yet",
            other_plant: "Different Plant?",
            not_plant: "No Leaf Found"
        };

        modalBadge.textContent = badges[type] || "Scan Result";
        modalTitle.textContent = data.title || data.disease_name || "Scan result";
        modalTitle.style.color = diagnosed ? "var(--accent-strong)" : "var(--text-primary)";
        modalDescription.textContent = result.message || "";

        // Reset sections
        modalMeta.replaceChildren();
        causesBox.replaceChildren();
        solutionsBox.replaceChildren();
        modalActions.replaceChildren();
        causesSection.style.display = "none";
        solutionsSection.style.display = "none";
        solutionsTitle.textContent = "Treatment and prevention";

        // Confidence bar, source and alternatives
        if (diagnosed) {

            if (Number.isFinite(percent)) {
                const row = make("div", "result-confidence");
                row.appendChild(make("span", "", "Confidence"));
                row.appendChild(make("strong", "", `${percent.toFixed(1)}%`));
                modalMeta.appendChild(row);

                const track = make("div", "crop-progress-track");
                const fill = make("div", `crop-progress-fill ${confidenceClass(percent)}`);
                fill.style.width = `${Math.max(0, Math.min(100, percent))}%`;
                track.appendChild(fill);
                modalMeta.appendChild(track);
            }

            if (data.source) {
                modalMeta.appendChild(make("div", "result-source", `Source: ${data.source}`));
            }

            if (Array.isArray(data.alternatives) && data.alternatives.length) {
                const names = data.alternatives
                    .map((alt) => `${alt.name} (${Number(alt.confidence).toFixed(0)}%)`)
                    .join(", ");
                modalMeta.appendChild(make("div", "result-alternatives", `Also possible: ${names}`));
            }
        }

        // Details from the online model
        if (data.description) {
            causesBox.textContent = data.description;
            causesSection.style.display = "block";
        }

        if (Array.isArray(data.treatment_sections) && data.treatment_sections.length) {
            renderTreatment(solutionsBox, data.treatment_sections);
            solutionsSection.style.display = "block";
        }

        // Not sure / wrong plant / no leaf: give guidance instead of a guess
        if (!diagnosed && Array.isArray(data.tips) && data.tips.length) {
            solutionsTitle.textContent = "How to get a better scan";
            const list = make("ul");
            data.tips.forEach((tip) => list.appendChild(make("li", "", tip)));
            solutionsBox.appendChild(list);
            solutionsSection.style.display = "block";
        }

        // Local CNN disease result: offer treatment advice from the chatbot
        if (type === "disease") {

            const adviceButton = make("button", "btn", "Get treatment advice");
            adviceButton.type = "button";

            adviceButton.addEventListener("click", () => {
                solutionsTitle.textContent = "Treatment and prevention";
                solutionsSection.style.display = "block";
                loadAdvice(data.plant_name || "crop", data.disease_name, adviceButton, solutionsBox);
            });

            modalActions.appendChild(adviceButton);
        }

        openModal();
    }

    // ------------------------------------------------------------------
    // Busy state
    // ------------------------------------------------------------------
    function setBusy(state) {
        busy = state;
        if (!submitButton) return;
        submitButton.disabled = state;
        submitButton.textContent = state ? "Analysing..." : "Detect";
    }

    // ------------------------------------------------------------------
    // Submit
    // ------------------------------------------------------------------
    form.addEventListener("submit", async (event) => {

        event.preventDefault();

        if (busy) return;

        clearStatus("uploadStatus");

        if (!plantSelect.value) {
            setStatus("uploadStatus", "error", "Please choose the plant first.");
            plantSelect.focus();
            return;
        }

        if (!fileInput.files[0]) {
            setStatus("uploadStatus", "error", "Please choose a leaf image first.");
            return;
        }

        setBusy(true);
        setStatus("uploadStatus", "info", "Analysing your leaf image. This can take a few seconds...");

        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 60000);

        try {

            const response = await fetch("/predict_disease", {
                method: "POST",
                body: new FormData(form),
                signal: controller.signal
            });

            const result = await parseJsonResponse(response);

            if (result.status === "success" && result.data) {

                renderDiagnosis(result);

                const type = result.data.result_type;
                const ok = type === "disease" || type === "healthy" || type === "online";

                setStatus("uploadStatus", ok ? "success" : "info",
                    ok ? "Scan complete." : "Scan complete, but no reliable diagnosis could be made.");
                return;
            }

            throw new Error(result.message || "Disease detection failed.");

        } catch (error) {

            console.error("Disease detection failed:", error);

            const message = error.name === "AbortError"
                ? "The scan took too long. Please try again."
                : (error.message || "Unable to complete disease detection.");

            setStatus("uploadStatus", "error", message);

        } finally {
            clearTimeout(timer);
            setBusy(false);
        }
    });

    // ------------------------------------------------------------------
    // Reset
    // ------------------------------------------------------------------
    form.addEventListener("reset", () => {
        clearStatus("uploadStatus");
        resetPreview();
        closeModal();
    });
}


// ============================================================================
// CHATBOT (text + image)
// ============================================================================

function setupChatbot() {

    const form = document.getElementById("chatbotForm");
    const input = document.getElementById("userInput");
    const chatLog = document.getElementById("chatLog");
    const imageInput = document.getElementById("chatImageInput");
    const imageName = document.getElementById("chatImageName");
    const imageClear = document.getElementById("chatImageClear");
    const chatPreviewBar = document.getElementById("chatPreviewBar");
    const chatPreviewImg = document.getElementById("chatPreviewImg");

    if (!form || !input || !chatLog) return;

    let attachedFile = null;
    let previewObjectUrl = "";

    if (imageInput) {
        imageInput.addEventListener("change", () => {

            const file = imageInput.files[0];
            if (!file) return;

            attachedFile = file;

            if (previewObjectUrl) URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = URL.createObjectURL(file);

            if (imageName) imageName.textContent = file.name;
            if (imageClear) imageClear.style.display = "block";
            if (chatPreviewBar) chatPreviewBar.classList.add("active");
            if (chatPreviewImg) {
                chatPreviewImg.src = previewObjectUrl;
                chatPreviewImg.classList.add("active");
            }
        });
    }

    function clearAttachedImage() {

        attachedFile = null;

        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl);
            previewObjectUrl = "";
        }

        if (imageInput) imageInput.value = "";
        if (imageName) imageName.textContent = "";
        if (imageClear) imageClear.style.display = "none";
        if (chatPreviewBar) chatPreviewBar.classList.remove("active");
        if (chatPreviewImg) {
            chatPreviewImg.src = "";
            chatPreviewImg.classList.remove("active");
        }
    }

    if (imageClear) imageClear.addEventListener("click", clearAttachedImage);

    form.addEventListener("submit", async (event) => {

        event.preventDefault();
        clearStatus("chatStatus");

        const message = input.value.trim();
        const hasImage = !!attachedFile;

        if (!message && !hasImage) {
            setStatus("chatStatus", "error", "Type a message or attach an image before sending.");
            return;
        }

        const capturedFile = attachedFile;
        const capturedUrl = previewObjectUrl;

        appendChatBubble(
            chatLog,
            message || "📷 Image sent for diagnosis",
            "user",
            hasImage ? capturedUrl : null
        );

        input.value = "";

        // The preview URL is still shown in the chat bubble, so detach it
        // from the attachment state without revoking it yet.
        attachedFile = null;
        previewObjectUrl = "";
        if (imageInput) imageInput.value = "";
        if (imageName) imageName.textContent = "";
        if (imageClear) imageClear.style.display = "none";
        if (chatPreviewBar) chatPreviewBar.classList.remove("active");
        if (chatPreviewImg) {
            chatPreviewImg.src = "";
            chatPreviewImg.classList.remove("active");
        }

        setStatus("chatStatus", "info", "Agribot is analysing...");

        try {

            let result;

            if (hasImage) {

                const formData = new FormData();
                formData.append("image", capturedFile);
                if (message) formData.append("message", message);

                const response = await fetch("/chatbot/image", {
                    method: "POST",
                    body: formData
                });
                result = await parseJsonResponse(response);

            } else {

                const response = await fetch("/chatbot", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message })
                });
                result = await parseJsonResponse(response);
            }

            let reply = result.data || result.message || "No response received.";

            if (typeof reply === "object" && reply !== null) {
                reply = reply.response || reply.message || reply.answer ||
                    reply.reply || JSON.stringify(reply);
            }

            appendChatBubble(chatLog, String(reply), "bot");

            if (result.status === "success") {
                clearStatus("chatStatus");
            } else {
                setStatus("chatStatus", "error", result.message || "Chatbot request failed.");
            }

        } catch (error) {

            console.error("Chatbot request failed:", error);
            appendChatBubble(chatLog, "Something went wrong. Please try again.", "bot");
            setStatus("chatStatus", "error", "Server error. Please try again.");
        }
    });

    form.addEventListener("reset", () => {
        clearStatus("chatStatus");
        clearAttachedImage();
    });
}

function appendChatBubble(log, message, type, imageUrl = null) {

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${type}`;

    if (imageUrl) {

        const img = document.createElement("img");
        img.src = imageUrl;
        img.alt = "Attached image";
        img.className = "chat-img-preview";
        bubble.appendChild(img);

        if (message && message !== "📷 Image sent for diagnosis") {
            const text = document.createElement("span");
            text.textContent = message;
            bubble.appendChild(text);
        }

    } else {
        bubble.textContent = message;
    }

    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
}


// ============================================================================
// WEATHER + FARMER ADVISORY
// ============================================================================

function setupWeather() {

    const locationPermission = document.getElementById("locationPermission");
    const enableLocationBtn = document.getElementById("enableLocationBtn");
    const locationLoading = document.getElementById("locationLoading");
    const weatherDashboard = document.getElementById("weatherDashboard");
    const locationError = document.getElementById("locationError");
    const locationErrorMessage = document.getElementById("locationErrorMessage");
    const retryLocationBtn = document.getElementById("retryLocationBtn");
    const refreshWeatherBtn = document.getElementById("refreshWeatherBtn");

    // Weather section does not exist on other pages.
    if (!locationPermission) return;

    let currentLatitude = null;
    let currentLongitude = null;

    // ------------------------------------------------------------------
    // Panel visibility.
    // Uses inline display (which beats the #id rules in style.css and the
    // inline style="display:none" in index.html).
    // ------------------------------------------------------------------
    function showState(state) {
        const panels = {
            permission: locationPermission,
            loading: locationLoading,
            dashboard: weatherDashboard,
            error: locationError
        };
        Object.entries(panels).forEach(([name, element]) => {
            if (!element) return;
            const shown = name === "dashboard" ? "grid" : "block";
            element.style.display = name === state ? shown : "none";
        });
    }

    function showLocationError(message) {
        if (locationErrorMessage) locationErrorMessage.textContent = message;
        showState("error");
    }

    // ------------------------------------------------------------------
    // Weather codes
    // ------------------------------------------------------------------
    const WEATHER_CODES = {
        0: { text: "Clear sky", icon: "☀️" },
        1: { text: "Mainly clear", icon: "🌤️" },
        2: { text: "Partly cloudy", icon: "⛅" },
        3: { text: "Overcast", icon: "☁️" },
        45: { text: "Foggy", icon: "🌫️" },
        48: { text: "Foggy", icon: "🌫️" },
        51: { text: "Light drizzle", icon: "🌦️" },
        53: { text: "Moderate drizzle", icon: "🌦️" },
        55: { text: "Heavy drizzle", icon: "🌧️" },
        56: { text: "Light freezing drizzle", icon: "🌧️" },
        57: { text: "Heavy freezing drizzle", icon: "🌧️" },
        61: { text: "Light rain", icon: "🌦️" },
        63: { text: "Moderate rain", icon: "🌧️" },
        65: { text: "Heavy rain", icon: "🌧️" },
        66: { text: "Light freezing rain", icon: "🌧️" },
        67: { text: "Heavy freezing rain", icon: "🌧️" },
        71: { text: "Light snowfall", icon: "🌨️" },
        73: { text: "Moderate snowfall", icon: "🌨️" },
        75: { text: "Heavy snowfall", icon: "❄️" },
        77: { text: "Snow grains", icon: "❄️" },
        80: { text: "Light rain showers", icon: "🌦️" },
        81: { text: "Moderate rain showers", icon: "🌧️" },
        82: { text: "Heavy rain showers", icon: "⛈️" },
        85: { text: "Light snow showers", icon: "🌨️" },
        86: { text: "Heavy snow showers", icon: "❄️" },
        95: { text: "Thunderstorm", icon: "⛈️" },
        96: { text: "Thunderstorm with hail", icon: "⛈️" },
        99: { text: "Severe thunderstorm with hail", icon: "⛈️" }
    };

    function getWeatherDescription(code) {
        return WEATHER_CODES[Number(code)] || { text: "Unknown conditions", icon: "🌤️" };
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) element.textContent = value;
    }

    function formatNumber(value, digits, suffix) {
        const number = Number(value);
        return Number.isFinite(number) ? `${number.toFixed(digits)}${suffix}` : "--";
    }

    // ------------------------------------------------------------------
    // Current conditions
    // ------------------------------------------------------------------
    function renderWeatherVitals(current, daily) {
        setText("weatherTemperature", formatNumber(current.temperature_2m, 1, "°C"));
        setText("weatherFeelsLike", formatNumber(current.apparent_temperature, 1, "°C"));
        setText("weatherHumidity", formatNumber(current.relative_humidity_2m, 0, "%"));
        setText("weatherRainfall", formatNumber(current.precipitation, 1, " mm"));
        setText("weatherWind", formatNumber(current.wind_speed_10m, 1, " km/h"));
        setText("weatherWindGust", formatNumber(current.wind_gusts_10m, 1, " km/h"));
        setText("weatherUV", formatNumber(current.uv_index, 1, ""));
        setText("weatherCloud", formatNumber(current.cloud_cover, 0, "%"));
        setText("weatherPressure", formatNumber(current.pressure_msl, 0, " hPa"));
        setText("weatherRainChance",
            formatNumber(daily.precipitation_probability_max?.[0], 0, "%"));
    }

    // ------------------------------------------------------------------
    // Farmer advisories
    // ------------------------------------------------------------------
    function renderFarmerAdvisories(current, daily) {

        const container = document.getElementById("farmerAdvisories");
        if (!container) return;

        const temperature = Number(current.temperature_2m);
        const humidity = Number(current.relative_humidity_2m);
        const precipitation = Number(current.precipitation);
        const wind = Number(current.wind_speed_10m);
        const uv = Number(current.uv_index);
        const rainChance = Number(daily.precipitation_probability_max?.[0]);
        const et0 = Number(daily.et0_fao_evapotranspiration?.[0]);

        const advisories = [];

        if (Number.isFinite(temperature) && temperature >= 35) {
            advisories.push({
                type: "warning", icon: "🌡️", title: "High temperature",
                message: `The current temperature is around ${temperature.toFixed(1)}°C. ` +
                    "Watch crops for heat stress and maintain appropriate soil moisture."
            });
        }

        if (Number.isFinite(temperature) && temperature <= 12) {
            advisories.push({
                type: "warning", icon: "🥶", title: "Low temperature",
                message: `The current temperature is around ${temperature.toFixed(1)}°C. ` +
                    "Protect temperature-sensitive crops from possible cold stress."
            });
        }

        if (Number.isFinite(humidity) && humidity >= 85) {
            advisories.push({
                type: "warning", icon: "💧", title: "High humidity",
                message: `Humidity is ${humidity.toFixed(0)}%. High humidity can increase fungal ` +
                    "disease risk. Monitor leaves closely and avoid unnecessary overhead irrigation."
            });
        }

        if (Number.isFinite(rainChance) && rainChance >= 60) {
            advisories.push({
                type: "info", icon: "🌧️", title: "Rain expected",
                message: `There is approximately a ${rainChance.toFixed(0)}% chance of rain today. ` +
                    "Consider postponing irrigation and protect harvested produce from moisture."
            });
        }

        if (Number.isFinite(precipitation) && precipitation > 0) {
            advisories.push({
                type: "warning", icon: "☔", title: "Rainfall occurring",
                message: `Current precipitation is around ${precipitation.toFixed(1)} mm. ` +
                    "Check field drainage and avoid unnecessary irrigation."
            });
        }

        if (Number.isFinite(wind) && wind >= 30) {
            advisories.push({
                type: "warning", icon: "💨", title: "Strong winds",
                message: `Wind speed is around ${wind.toFixed(1)} km/h. Avoid spraying pesticides ` +
                    "or foliar nutrients in strong wind and secure vulnerable plants."
            });
        }

        if (Number.isFinite(uv) && uv >= 7) {
            advisories.push({
                type: "info", icon: "☀️", title: "High UV conditions",
                message: `The UV index is ${uv.toFixed(1)}. Schedule field work and spraying ` +
                    "during cooler periods where practical."
            });
        }

        if (Number.isFinite(et0) && et0 >= 5) {
            advisories.push({
                type: "info", icon: "💦", title: "High water demand",
                message: `Estimated evapotranspiration is ${et0.toFixed(1)} mm. Monitor soil ` +
                    "moisture and adjust irrigation according to crop and soil conditions."
            });
        }

        if (!advisories.length) {
            advisories.push({
                type: "good", icon: "🌱", title: "Good farming conditions",
                message: "Current weather conditions appear relatively stable for routine " +
                    "agricultural activities. Continue monitoring your crop and soil conditions."
            });
        }

        container.innerHTML = advisories.map((advisory) => `
            <div class="farmer-advisory ${advisory.type}">
                <div class="farmer-advisory-icon">${advisory.icon}</div>
                <div class="farmer-advisory-content">
                    <h4>${advisory.title}</h4>
                    <p>${advisory.message}</p>
                </div>
            </div>
        `).join("");
    }

    // ------------------------------------------------------------------
    // 7-day forecast
    // ------------------------------------------------------------------
    function renderForecast(daily) {

        const container = document.getElementById("weatherForecast");
        if (!container) return;

        const dates = daily.time || [];

        if (!dates.length) {
            container.innerHTML =
                `<div class="weather-advisory-loading">Forecast unavailable.</div>`;
            return;
        }

        container.innerHTML = dates.map((date, index) => {

            const weather = getWeatherDescription(daily.weather_code?.[index]);
            const dateObject = new Date(`${date}T00:00:00`);

            const day = dateObject.toLocaleDateString("en-IN", { weekday: "short" });
            const formattedDate = dateObject.toLocaleDateString("en-IN",
                { day: "numeric", month: "short" });

            return `
                <div class="weather-forecast-card">
                    <div class="forecast-day">${day}</div>
                    <div class="forecast-date">${formattedDate}</div>
                    <div class="forecast-icon">${weather.icon}</div>
                    <div class="forecast-condition">${weather.text}</div>
                    <div class="forecast-temperature">
                        ${formatNumber(daily.temperature_2m_max?.[index], 0, "°")}
                        /
                        ${formatNumber(daily.temperature_2m_min?.[index], 0, "°")}
                    </div>
                    <div class="forecast-rain">
                        🌧️ ${formatNumber(daily.precipitation_probability_max?.[index], 0, "%")}
                    </div>
                    <div class="forecast-rain-amount">
                        ${formatNumber(daily.precipitation_sum?.[index], 1, " mm")}
                    </div>
                    <div class="forecast-details">
                        💨 ${formatNumber(daily.wind_speed_10m_max?.[index], 0, " km/h")}
                        &nbsp;&nbsp;
                        ☀️ ${formatNumber(daily.uv_index_max?.[index], 1, "")}
                    </div>
                </div>
            `;
        }).join("");
    }

    // ------------------------------------------------------------------
    // Render everything
    // ------------------------------------------------------------------
    function renderWeather(data) {

        if (!data || data.status !== "success") {
            throw new Error(data?.message || "Invalid weather response.");
        }

        const location = data.location || {};
        const current = data.current || {};
        const daily = data.daily || {};

        const latitude = Number(location.latitude);
        const longitude = Number(location.longitude);
        const timezone = location.timezone || "Local time";

        setText("weatherLocationName", "Weather at your location");

        const coords =
            Number.isFinite(latitude) && Number.isFinite(longitude)
                ? `📍 ${latitude.toFixed(4)}, ${longitude.toFixed(4)} (${timezone})`
                : "📍 Your current location";

        const updatedText = current.time
            ? `Updated ${new Date(current.time).toLocaleString("en-IN", {
                day: "numeric", month: "short", hour: "numeric", minute: "2-digit"
            })}`
            : "Live weather data";

        // CSS (white-space: pre-line) turns the \n into a line break.
        setText("weatherUpdated", `${coords}\n${updatedText}`);

        renderWeatherVitals(current, daily);
        renderFarmerAdvisories(current, daily);
        renderForecast(daily);

        showState("dashboard");
    }

    // ------------------------------------------------------------------
    // Call the Flask weather route
    // ------------------------------------------------------------------
    async function fetchWeather(latitude, longitude) {

        const url = `/api/weather?latitude=${encodeURIComponent(latitude)}` +
            `&longitude=${encodeURIComponent(longitude)}`;

        const response = await fetch(url, {
            method: "GET",
            headers: { "Accept": "application/json" },
            cache: "no-store"
        });

        let data;
        try {
            data = await response.json();
        } catch (error) {
            throw new Error(
                `Weather server returned an invalid response (HTTP ${response.status}). ` +
                "Check that the /api/weather route exists."
            );
        }

        if (!response.ok || data.status !== "success") {
            throw new Error(data.message || "Unable to retrieve live weather.");
        }

        return data;
    }

    // ------------------------------------------------------------------
    // Ask the browser for the user's location
    // ------------------------------------------------------------------
    function requestUserLocation() {

        console.log("Agribot: Enable Location clicked");

        if (!window.isSecureContext) {
            showLocationError(
                "Location only works on a secure page. Open the app at " +
                "http://127.0.0.1:5000 or http://localhost:5000 (not a network IP address)."
            );
            return;
        }

        if (!navigator.geolocation) {
            showLocationError(
                "Your browser does not support location services. Please use Chrome, Safari or Edge."
            );
            return;
        }

        showState("loading");

        navigator.geolocation.getCurrentPosition(

            async (position) => {

                currentLatitude = position.coords.latitude;
                currentLongitude = position.coords.longitude;

                console.log("Agribot: location received",
                    currentLatitude, currentLongitude);

                try {
                    renderWeather(await fetchWeather(currentLatitude, currentLongitude));
                } catch (error) {
                    console.error("Agribot: weather request failed:", error);
                    showLocationError(
                        error.message || "Unable to load weather data for your location."
                    );
                }
            },

            (error) => {

                console.error("Agribot: geolocation error", error);

                const messages = {
                    1: "Location permission was denied. Allow location for this site " +
                        "(lock icon in the address bar) and also enable Location Services " +
                        "for your browser in macOS System Settings → Privacy & Security.",
                    2: "Your location could not be determined. Make sure Location Services " +
                        "are turned on for your Mac and your browser.",
                    3: "Getting your location took too long. Please try again."
                };

                showLocationError(
                    messages[error.code] || "An unknown location error occurred. Please try again."
                );
            },

            // Laptops locate via Wi-Fi, so high accuracy only slows things down.
            { enableHighAccuracy: false, timeout: 20000, maximumAge: 300000 }
        );
    }

    // ------------------------------------------------------------------
    // Buttons
    // ------------------------------------------------------------------
    if (enableLocationBtn) enableLocationBtn.addEventListener("click", requestUserLocation);
    if (retryLocationBtn) retryLocationBtn.addEventListener("click", requestUserLocation);

    if (refreshWeatherBtn) {
        refreshWeatherBtn.addEventListener("click", async () => {

            if (currentLatitude === null || currentLongitude === null) {
                requestUserLocation();
                return;
            }

            const originalText = refreshWeatherBtn.textContent;
            refreshWeatherBtn.disabled = true;
            refreshWeatherBtn.textContent = "Refreshing...";

            try {
                renderWeather(await fetchWeather(currentLatitude, currentLongitude));
            } catch (error) {
                console.error("Weather refresh failed:", error);
                showLocationError(error.message || "Unable to refresh weather.");
            } finally {
                refreshWeatherBtn.disabled = false;
                refreshWeatherBtn.textContent = originalText;
            }
        });
    }

    // Initial state
    showState("permission");
}