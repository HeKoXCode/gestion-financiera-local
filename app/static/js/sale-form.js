(() => {
    "use strict";

    const form = document.querySelector("#sale-form");
    if (!form) return;

    const productPriceInput = document.querySelector("#id_cash_price");
    const downPaymentInput = document.querySelector("#id_down_payment");
    const downPaymentMethodInput = document.querySelector("#id_down_payment_method");
    const customInstallmentTotalInput = document.querySelector(
        "#id_custom_installment_total"
    );
    const financedInput = document.querySelector("#id_financed_amount");
    const countInput = document.querySelector("#id_installment_count");
    const frequencyInput = document.querySelector("#id_frequency");
    const firstDueInput = document.querySelector("#id_first_due_date");
    const productInput = document.querySelector("#id_product");
    const descriptionInput = document.querySelector("#id_product_description");
    const totalOutput = document.querySelector("#preview-total");
    const productPriceOutput = document.querySelector("#preview-product-price");
    const downPaymentOutput = document.querySelector("#preview-down-payment");
    const baseBalanceOutput = document.querySelector("#preview-base-balance");
    const adjustmentLabel = document.querySelector("#preview-adjustment-label");
    const adjustmentOutput = document.querySelector("#preview-adjustment");
    const operationTotalOutput = document.querySelector("#preview-operation-total");
    const financingModeNote = document.querySelector("#financing-mode-note");
    const captionOutput = document.querySelector("#preview-caption");
    const frequencyOutput = document.querySelector("#preview-frequency");
    const rowsOutput = document.querySelector("#preview-rows");
    const emptyOutput = document.querySelector("#preview-empty");
    const tableOutput = document.querySelector("#preview-table-wrap");
    const submitButton = document.querySelector("#sale-submit");
    let lastAutomaticDescription = "";

    const currency = new Intl.NumberFormat("es-AR", {
        style: "currency",
        currency: "ARS",
        minimumFractionDigits: 2,
    });
    const dateFormat = new Intl.DateTimeFormat("es-AR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "UTC",
    });

    function parseMoneyToCents(rawValue) {
        let value = String(rawValue || "").trim().replace(/\s/g, "").replace(/\$/g, "");
        if (!value) return 0;

        if (value.includes(",") && value.includes(".")) {
            value = value.replace(/\./g, "").replace(",", ".");
        } else if (value.includes(",")) {
            value = value.replace(/\./g, "").replace(",", ".");
        } else if (/^\d{1,3}(\.\d{3})+$/.test(value)) {
            value = value.replace(/\./g, "");
        }

        const numeric = Number(value);
        return Number.isFinite(numeric) && numeric > 0 ? Math.round(numeric * 100) : 0;
    }

    function dateFromIso(value) {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return null;
        const [year, month, day] = value.split("-").map(Number);
        return new Date(Date.UTC(year, month - 1, day));
    }

    function addUtcMonths(anchor, months) {
        const monthIndex = anchor.getUTCMonth() + months;
        const year = anchor.getUTCFullYear() + Math.floor(monthIndex / 12);
        const month = ((monthIndex % 12) + 12) % 12;
        const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
        return new Date(
            Date.UTC(year, month, Math.min(anchor.getUTCDate(), lastDay))
        );
    }

    function updatePreview() {
        const productPriceCents = parseMoneyToCents(productPriceInput.value);
        const downPaymentCents = parseMoneyToCents(downPaymentInput.value);
        const totalCents = parseMoneyToCents(financedInput.value);
        const baseBalanceCents = Math.max(productPriceCents - downPaymentCents, 0);
        const operationTotalCents = downPaymentCents + totalCents;
        const adjustmentCents = operationTotalCents - productPriceCents;
        const count = Number.parseInt(countInput.value, 10);
        const firstDate = dateFromIso(firstDueInput.value);
        const isMonthly = frequencyInput.value === "monthly";
        const interval = frequencyInput.value === "biweekly" ? 14 : 7;
        const frequencyLabel =
            frequencyInput.options[frequencyInput.selectedIndex]?.text || "Sin datos";

        totalOutput.textContent = currency.format(totalCents / 100);
        productPriceOutput.textContent = currency.format(productPriceCents / 100);
        downPaymentOutput.textContent = currency.format(downPaymentCents / 100);
        baseBalanceOutput.textContent = currency.format(baseBalanceCents / 100);
        operationTotalOutput.textContent = currency.format(operationTotalCents / 100);
        adjustmentOutput.textContent = currency.format(Math.abs(adjustmentCents) / 100);
        adjustmentLabel.textContent =
            adjustmentCents > 0
                ? "Costo de financiación"
                : adjustmentCents < 0
                  ? "Descuento en cuotas"
                  : "Ajuste por financiación";
        frequencyOutput.textContent = frequencyLabel;

        if (!totalCents || !count || count < 1 || !firstDate) {
            captionOutput.textContent = "Completá monto, cantidad y primera fecha.";
            emptyOutput.hidden = false;
            tableOutput.hidden = true;
            rowsOutput.replaceChildren();
            return;
        }

        const regularCents = Math.floor(totalCents / count);
        if (regularCents < 1) {
            captionOutput.textContent = "El monto es demasiado pequeño para esta cantidad.";
            emptyOutput.hidden = false;
            tableOutput.hidden = true;
            return;
        }

        const fragment = document.createDocumentFragment();
        for (let number = 1; number <= count; number += 1) {
            const amountCents =
                number === count ? totalCents - regularCents * (count - 1) : regularCents;
            const dueDate = isMonthly ? addUtcMonths(firstDate, number - 1) : new Date(firstDate);
            if (!isMonthly) {
                dueDate.setUTCDate(firstDate.getUTCDate() + (number - 1) * interval);
            }

            const row = document.createElement("tr");
            const numberCell = document.createElement("td");
            const dateCell = document.createElement("td");
            const amountCell = document.createElement("td");
            numberCell.textContent = `${number}/${count}`;
            dateCell.textContent = dateFormat.format(dueDate);
            amountCell.textContent = currency.format(amountCents / 100);
            row.append(numberCell, dateCell, amountCell);
            fragment.append(row);
        }

        rowsOutput.replaceChildren(fragment);
        captionOutput.textContent = isMonthly
            ? `${count} cuotas · una por mes`
            : `${count} cuotas · cada ${interval} días`;
        emptyOutput.hidden = true;
        tableOutput.hidden = false;
    }

    function synchronizeFinancing() {
        const productPriceCents = parseMoneyToCents(productPriceInput.value);
        const downPaymentCents = parseMoneyToCents(downPaymentInput.value);
        const suggestedCents = Math.max(productPriceCents - downPaymentCents, 0);
        const usesCustomTotal = customInstallmentTotalInput.checked;

        if (!usesCustomTotal) {
            financedInput.value =
                suggestedCents > 0
                    ? (suggestedCents / 100).toFixed(2).replace(".", ",")
                    : "";
        }
        financedInput.readOnly = !usesCustomTotal;
        financedInput.required = usesCustomTotal;
        financedInput.classList.toggle("is-calculated", !usesCustomTotal);
        financedInput.setAttribute("aria-readonly", String(!usesCustomTotal));
        financingModeNote.textContent = usesCustomTotal
            ? "Total elegido: no se recalcula al modificar el precio o el pago inicial."
            : "Cálculo automático: precio del producto menos pago inicial.";

        const hasDownPayment = downPaymentCents > 0;
        downPaymentMethodInput.disabled = !hasDownPayment;
        downPaymentMethodInput.required = hasDownPayment;
        if (!hasDownPayment) downPaymentMethodInput.value = "";
        updatePreview();
    }

    function updateProductDescription() {
        const selectedText =
            productInput.options[productInput.selectedIndex]?.text?.trim() || "";
        const current = descriptionInput.value.trim();
        if (!current || current === lastAutomaticDescription) {
            descriptionInput.value = selectedText.startsWith("Seleccionar") ? "" : selectedText;
            lastAutomaticDescription = descriptionInput.value;
        }
    }

    [countInput, frequencyInput, firstDueInput].forEach((control) => {
        control?.addEventListener("input", updatePreview);
        control?.addEventListener("change", updatePreview);
    });
    financedInput?.addEventListener("input", updatePreview);
    financedInput?.addEventListener("change", updatePreview);
    [productPriceInput, downPaymentInput].forEach((control) => {
        control?.addEventListener("input", synchronizeFinancing);
        control?.addEventListener("change", synchronizeFinancing);
    });
    customInstallmentTotalInput?.addEventListener("change", synchronizeFinancing);
    productInput?.addEventListener("change", updateProductDescription);

    form.addEventListener("submit", () => {
        // This is synchronous: the latest visible values are copied before the
        // browser builds the POST request. The server recalculates them again.
        synchronizeFinancing();
        if (submitButton && form.checkValidity()) {
            submitButton.disabled = true;
            submitButton.textContent = "Guardando venta…";
        }
    });

    synchronizeFinancing();
})();
