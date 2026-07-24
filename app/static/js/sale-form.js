(() => {
    "use strict";

    const form = document.querySelector("#sale-form");
    if (!form) return;

    const financedInput = document.querySelector("#id_financed_amount");
    const countInput = document.querySelector("#id_installment_count");
    const frequencyInput = document.querySelector("#id_frequency");
    const firstDueInput = document.querySelector("#id_first_due_date");
    const productInput = document.querySelector("#id_product");
    const descriptionInput = document.querySelector("#id_product_description");
    const totalOutput = document.querySelector("#preview-total");
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

    function updatePreview() {
        const totalCents = parseMoneyToCents(financedInput.value);
        const count = Number.parseInt(countInput.value, 10);
        const firstDate = dateFromIso(firstDueInput.value);
        const interval = frequencyInput.value === "biweekly" ? 14 : 7;
        const frequencyLabel =
            frequencyInput.options[frequencyInput.selectedIndex]?.text || "Sin datos";

        totalOutput.textContent = currency.format(totalCents / 100);
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
            const dueDate = new Date(firstDate);
            dueDate.setUTCDate(firstDate.getUTCDate() + (number - 1) * interval);

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
        captionOutput.textContent = `${count} cuotas · cada ${interval} días`;
        emptyOutput.hidden = true;
        tableOutput.hidden = false;
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

    [financedInput, countInput, frequencyInput, firstDueInput].forEach((control) => {
        control?.addEventListener("input", updatePreview);
        control?.addEventListener("change", updatePreview);
    });
    productInput?.addEventListener("change", updateProductDescription);

    form.addEventListener("submit", () => {
        if (submitButton && form.checkValidity()) {
            submitButton.disabled = true;
            submitButton.textContent = "Guardando venta…";
        }
    });

    updatePreview();
})();

