// ==========================================================================
// AGRIBOT - Lightweight Client Validation
// --------------------------------------------------------------------------
// This helper keeps validation small and dependency-free. It uses existing
// HTML constraints and adds a few ergonomic checks for cleaner feedback.
// ==========================================================================

window.AgribotValidation = (() => {
    function validateForm(form) {
        const fields = Array.from(form.querySelectorAll("input, textarea, select"));
        let isValid = true;

        fields.forEach((field) => {
            resetFieldState(field);

            if (!validateField(field)) {
                isValid = false;
            }
        });

        return isValid;
    }

    function validateField(field) {
        const value = field.value.trim();

        if (field.required && !value) {
            markInvalid(field);
            return false;
        }

        if (field.type === "email" && value) {
            const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailPattern.test(value)) {
                markInvalid(field);
                return false;
            }
        }

        if (field.name === "password" && value) {
            const hasUpper = /[A-Z]/.test(value);
            const hasLower = /[a-z]/.test(value);
            const hasDigit = /\d/.test(value);
            const hasSymbol = /[^A-Za-z0-9]/.test(value);

            if (value.length < 8 || !hasUpper || !hasLower || !hasDigit || !hasSymbol) {
                markInvalid(field);
                return false;
            }
        }

        return true;
    }

    function markInvalid(field) {
        field.style.borderColor = "rgba(186, 78, 94, 0.65)";
        field.style.boxShadow = "0 0 0 4px rgba(186, 78, 94, 0.12)";
    }

    function resetFieldState(field) {
        field.style.borderColor = "";
        field.style.boxShadow = "";
    }

    return {
        validateForm,
        validateField
    };
})();
