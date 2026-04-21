// ==========================================================================
// AGRIBOT - Authentication Flows
// --------------------------------------------------------------------------
// Shared logic for login and registration with lightweight validation and
// visual status feedback that matches the glassmorphism UI.
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
    setupAuthNavigation();
    setupRevealAnimations();
    setupLoginForm();
    setupRegisterForm();
});

function setupAuthNavigation() {
    const toggle = document.querySelector("[data-nav-toggle]");
    const menu = document.querySelector("[data-nav-menu]");

    if (!toggle || !menu) {
        return;
    }

    toggle.addEventListener("click", () => {
        menu.classList.toggle("is-open");
    });
}

function showAuthStatus(type, message) {
    const status = document.getElementById("authStatus");

    if (!status) {
        return;
    }

    status.className = "status-banner visible";
    status.classList.add(type);
    status.textContent = message;
}

function clearAuthStatus() {
    const status = document.getElementById("authStatus");

    if (!status) {
        return;
    }

    status.className = "status-banner";
    status.textContent = "";
}

function setupRevealAnimations() {
    const revealItems = document.querySelectorAll("[data-reveal]");

    revealItems.forEach((item, index) => {
        window.setTimeout(() => {
            item.classList.add("is-visible");
        }, 80 * index);
    });
}

function setupLoginForm() {
    const loginForm = document.getElementById("loginForm");

    if (!loginForm) {
        return;
    }

    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearAuthStatus();

        if (!window.AgribotValidation.validateForm(loginForm)) {
            showAuthStatus("error", "Please complete every field correctly before logging in.");
            return;
        }

        const formData = new FormData(loginForm);
        const payload = {
            username: formData.get("username"),
            password: formData.get("password"),
            expected_role: loginForm.dataset.expectedRole || "user"
        };

        showAuthStatus("info", "Signing you in...");

        try {
            const response = await fetch("/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (response.ok && result.status === "success") {
                showAuthStatus("success", result.message || "Login successful. Redirecting...");
                window.location.href = result.redirect_to || "/";
                return;
            }

            showAuthStatus("error", result.message || "Invalid credentials. Please try again.");
        } catch (error) {
            console.error("Login request failed:", error);
            showAuthStatus("error", "Server error. Please try again.");
        }
    });
}

function setupRegisterForm() {
    const registerForm = document.getElementById("registerForm");

    if (!registerForm) {
        return;
    }

    registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        clearAuthStatus();

        if (!window.AgribotValidation.validateForm(registerForm)) {
            showAuthStatus("error", "Please fix the highlighted fields before registering.");
            return;
        }

        const formData = new FormData(registerForm);
        const payload = {
            name: formData.get("name"),
            city: formData.get("city"),
            email: formData.get("email"),
            username: formData.get("username"),
            password: formData.get("password")
        };

        showAuthStatus("info", "Creating your account...");

        try {
            const response = await fetch("/register", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const result = await response.json();

            if (response.ok && result.status === "success") {
                showAuthStatus("success", result.message || "Account created successfully. Redirecting to login...");
                window.location.href = "/login";
                return;
            }

            showAuthStatus("error", result.message || "Registration failed. Please try again.");
        } catch (error) {
            console.error("Registration request failed:", error);
            showAuthStatus("error", "Server error. Please try again.");
        }
    });
}
