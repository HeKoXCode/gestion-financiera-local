(() => {
    "use strict";

    const form = document.querySelector("#sale-form");
    if (!form) return;

    const operationTypeInputs = document.querySelectorAll("input[name='operation_type']");
    const productOnlyElements = document.querySelectorAll("[data-product-only]");
    const loanOnlyElements = document.querySelectorAll("[data-loan-only]");
    const productPriceInput = document.querySelector("#id_cash_price");
    const downPaymentInput = document.querySelector("#id_down_payment");
    const downPaymentMethodInput = document.querySelector("#id_down_payment_method");
    const loanDisbursementMethodInput = document.querySelector("#id_loan_disbursement_method");
    const loanInterestRateInput = document.querySelector("#id_loan_interest_rate");
    const customInstallmentTotalInput = document.querySelector(
        "#id_custom_installment_total"
    );
    const financedInput = document.querySelector("#id_financed_amount");
    const countInput = document.querySelector("#id_installment_count");
    const installmentAmountInput = document.querySelector("#id_installment_amount");
    const installmentCalculationNote = document.querySelector(
        "#installment-calculation-note"
    );
    const frequencyInput = document.querySelector("#id_frequency");
    const firstDueInput = document.querySelector("#id_first_due_date");
    const deliveryDateInput = document.querySelector("#id_delivery_date");
    const sameDayFirstDueInput = document.querySelector("#id_same_day_first_due");
    const deliveryInstallmentPanel = document.querySelector(
        "#delivery-installment-panel"
    );
    const deliveryInstallmentStatusInputs = document.querySelectorAll(
        "input[name='first_installment_delivery_status']"
    );
    const deliveryInstallmentMethodWrap = document.querySelector(
        "#delivery-installment-method"
    );
    const deliveryInstallmentMethodInput = document.querySelector(
        "#id_first_installment_payment_method"
    );
    const deliveryInstallmentSummary = document.querySelector(
        "#delivery-installment-summary"
    );
    const historicalPaidInput = document.querySelector("#id_historical_paid_installments");
    const historicalMethodInput = document.querySelector("#id_historical_payment_method");
    const historicalLateInput = document.querySelector(
        "#id_historical_late_installments"
    );
    const historicalLatePicker = document.querySelector("#historical-late-picker");
    const historicalInstallmentChips = document.querySelector(
        "#historical-installment-chips"
    );
    const historicalLateDetails = document.querySelector("#historical-late-details");
    const historicalLateCount = document.querySelector("#historical-late-count");
    const historicalLateFeedback = document.querySelector(
        "#historical-late-feedback"
    );
    const historicalSummary = document.querySelector("#historical-summary");
    const productInput = document.querySelector("#id_product");
    const descriptionInput = document.querySelector("#id_product_description");
    const totalOutput = document.querySelector("#preview-total");
    const productPriceOutput = document.querySelector("#preview-product-price");
    const downPaymentOutput = document.querySelector("#preview-down-payment");
    const baseBalanceOutput = document.querySelector("#preview-base-balance");
    const adjustmentLabel = document.querySelector("#preview-adjustment-label");
    const adjustmentOutput = document.querySelector("#preview-adjustment");
    const operationTotalOutput = document.querySelector("#preview-operation-total");
    const cashPriceLabel = document.querySelector("#cash-price-label");
    const financedAmountLabel = document.querySelector("#financed-amount-label");
    const operationDescriptionLabel = document.querySelector("#operation-description-label");
    const customTotalLabel = document.querySelector("#custom-total-label");
    const customTotalHelp = document.querySelector("#custom-total-help");
    const deliveryDateLabel = document.querySelector("#delivery-date-label");
    const sameDayDueLabel = document.querySelector("#same-day-due-label");
    const firstInstallmentPaidLabel = document.querySelector(
        "label[for='id_first_installment_delivery_status_0']"
    );
    const previewTotalLabel = document.querySelector("#preview-total-label");
    const previewPriceLabel = document.querySelector("#preview-price-label");
    const previewOperationTotalLabel = document.querySelector("#preview-operation-total-label");
    const financingModeNote = document.querySelector("#financing-mode-note");
    const captionOutput = document.querySelector("#preview-caption");
    const frequencyOutput = document.querySelector("#preview-frequency");
    const rowsOutput = document.querySelector("#preview-rows");
    const emptyOutput = document.querySelector("#preview-empty");
    const tableOutput = document.querySelector("#preview-table-wrap");
    const submitButton = document.querySelector("#sale-submit");
    const saleDraftLinks = document.querySelectorAll("[data-sale-draft-link]");
    const saleDraftKey = "gestion-financiera:nueva-venta-borrador";
    const today = dateFromIso(form.dataset.today);
    let lastAutomaticDescription = "";
    let historicalLateState = {};
    let applyingInstallmentCalculation = false;
    try {
        const initialLateState = JSON.parse(historicalLateInput?.value || "{}");
        if (initialLateState && typeof initialLateState === "object") {
            historicalLateState = initialLateState;
        }
    } catch (_error) {
        historicalLateState = {};
    }

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

    function parseLocalizedNumber(rawValue) {
        let value = String(rawValue || "").trim().replace(/\s/g, "");
        if (!value) return 0;
        if (value.includes(",") && value.includes(".")) {
            value = value.replace(/\./g, "").replace(",", ".");
        } else {
            value = value.replace(",", ".");
        }
        const numeric = Number(value);
        return Number.isFinite(numeric) && numeric >= 0 ? numeric : 0;
    }

    function operationType() {
        return document.querySelector("input[name='operation_type']:checked")?.value || "product";
    }

    function isLoan() {
        return operationType() === "loan";
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

    function plannedDueDates(firstDate, frequency, count) {
        if (!firstDate || !count || count < 1) return [];
        const isMonthly = frequency === "monthly";
        const interval = frequency === "biweekly" ? 14 : 7;
        return Array.from({ length: count }, (_, offset) => {
            if (isMonthly) return addUtcMonths(firstDate, offset);
            const dueDate = new Date(firstDate);
            dueDate.setUTCDate(firstDate.getUTCDate() + offset * interval);
            return dueDate;
        });
    }

    function deliveryInstallmentStatus() {
        return document.querySelector(
            "input[name='first_installment_delivery_status']:checked"
        )?.value || "";
    }

    function storeHistoricalLateState() {
        if (historicalLateInput) {
            historicalLateInput.value = JSON.stringify(historicalLateState);
        }
    }

    function selectedLateInstallments() {
        return Object.entries(historicalLateState)
            .map(([installment, days]) => [
                Number.parseInt(installment, 10),
                Number.parseInt(days, 10),
            ])
            .filter(([installment, days]) => installment > 0 && days > 0)
            .sort(([first], [second]) => first - second);
    }

    function updateHistoricalLateCount() {
        if (!historicalLateCount) return;
        const lateCount = selectedLateInstallments().length;
        historicalLateCount.textContent = lateCount
            ? `${lateCount} con atraso`
            : "Todas en fecha";
        historicalLateCount.classList.toggle("has-late-installments", lateCount > 0);
    }

    function showHistoricalLateFeedback(message = "") {
        if (!historicalLateFeedback) return;
        historicalLateFeedback.textContent = message;
        historicalLateFeedback.hidden = !message;
    }

    function renderHistoricalLatePicker(dueDates, paidCount, firstPaidAtDelivery) {
        if (
            !historicalLatePicker ||
            !historicalInstallmentChips ||
            !historicalLateDetails
        ) return;

        const visibleCount = Math.min(Math.max(paidCount, 0), dueDates.length);
        historicalLatePicker.hidden = visibleCount < 1;
        showHistoricalLateFeedback();
        Object.keys(historicalLateState).forEach((rawNumber) => {
            const number = Number.parseInt(rawNumber, 10);
            if (
                number < 1 ||
                number > visibleCount ||
                (number === 1 && firstPaidAtDelivery)
            ) {
                delete historicalLateState[rawNumber];
            }
        });
        storeHistoricalLateState();
        updateHistoricalLateCount();
        historicalInstallmentChips.replaceChildren();
        historicalLateDetails.replaceChildren();
        if (visibleCount < 1) return;

        const chips = document.createDocumentFragment();
        for (let number = 1; number <= visibleCount; number += 1) {
            const button = document.createElement("button");
            const wasPaidAtDelivery = number === 1 && firstPaidAtDelivery;
            const dueDate = dueDates[number - 1];
            const maximumDays = today
                ? Math.floor(
                    (today.getTime() - dueDate.getTime()) / 86400000
                )
                : 36500;
            const canBeLate = maximumDays > 0;
            const isLate = Boolean(historicalLateState[number]);
            const isNotDue = !wasPaidAtDelivery && maximumDays < 0;
            const isOnTime = !isLate && !isNotDue;
            button.type = "button";
            button.className = "historical-installment-chip";
            button.classList.toggle("is-late", isLate);
            button.classList.toggle("is-on-time", isOnTime);
            button.classList.toggle("is-not-due", isNotDue);
            button.dataset.unavailable = String(wasPaidAtDelivery || !canBeLate);
            button.dataset.status = isLate
                ? "late"
                : isNotDue
                  ? "not-due"
                  : "on-time";
            button.setAttribute("aria-pressed", String(isLate));
            button.textContent = isOnTime ? `${number} ✓` : String(number);
            button.title = wasPaidAtDelivery
                ? "Pagada el día de la entrega"
                : isNotDue
                  ? `Cuota ${number}: todavía no venció (${dateFormat.format(dueDate)})`
                  : !canBeLate
                    ? `Cuota ${number}: pagada en fecha; vence hoy`
                : isLate
                  ? `Cuota ${number}: quitar atraso`
                  : `Cuota ${number}: pagada en fecha; tocar para marcar atraso`;
            button.setAttribute("aria-label", button.title);
            button.addEventListener("click", () => {
                if (wasPaidAtDelivery) {
                    showHistoricalLateFeedback(
                        "La cuota 1 figura pagada el día de la entrega, por eso no puede tener atraso."
                    );
                    return;
                }
                if (!canBeLate) {
                    const isDueToday = today && dueDate.getTime() === today.getTime();
                    showHistoricalLateFeedback(
                        isDueToday
                            ? `La cuota ${number} vence hoy: todavía no puede tener días de atraso.`
                            : `La cuota ${number} todavía no venció (${dateFormat.format(dueDate)}). Revisá las fechas o la cantidad pagada.`
                    );
                    return;
                }
                showHistoricalLateFeedback();
                if (historicalLateState[number]) {
                    delete historicalLateState[number];
                } else {
                    historicalLateState[number] = 1;
                }
                storeHistoricalLateState();
                updatePreview();
                if (historicalLateState[number]) {
                    requestAnimationFrame(() => {
                        document.querySelector(
                            `[data-historical-late-days="${number}"]`
                        )?.focus();
                    });
                }
            });
            chips.append(button);
        }
        historicalInstallmentChips.append(chips);

        const details = document.createDocumentFragment();
        selectedLateInstallments().forEach(([number, days]) => {
            const maximumDays = today
                ? Math.max(
                    1,
                    Math.floor(
                        (today.getTime() - dueDates[number - 1].getTime()) / 86400000
                    )
                )
                : 36500;
            const row = document.createElement("label");
            const title = document.createElement("strong");
            const control = document.createElement("span");
            const input = document.createElement("input");
            const suffix = document.createElement("small");
            row.className = "historical-late-entry";
            title.textContent = `Cuota ${number}`;
            input.type = "number";
            input.min = "1";
            input.max = String(maximumDays);
            input.required = true;
            input.inputMode = "numeric";
            input.value = String(days);
            input.setAttribute("data-historical-late-days", String(number));
            input.setAttribute("aria-label", `Días de atraso de la cuota ${number}`);
            input.addEventListener("input", () => {
                historicalLateState[number] = Math.max(
                    Number.parseInt(input.value, 10) || 0,
                    0
                );
                storeHistoricalLateState();
            });
            input.addEventListener("change", updatePreview);
            suffix.textContent = "días tarde";
            control.append(input, suffix);
            row.append(title, control);
            details.append(row);
        });
        historicalLateDetails.append(details);
    }

    function updateHistoricalSummary(firstDate, frequency, count) {
        if (!historicalPaidInput || !historicalMethodInput || !historicalSummary) return;
        const paidCount = Math.max(Number.parseInt(historicalPaidInput.value, 10) || 0, 0);
        const firstPaidAtDelivery =
            Boolean(sameDayFirstDueInput?.checked) &&
            deliveryInstallmentStatus() === "paid";
        const firstPendingAtDelivery =
            Boolean(sameDayFirstDueInput?.checked) &&
            deliveryInstallmentStatus() === "pending";
        const dueDates = plannedDueDates(firstDate, frequency, count);
        const dueCount = today
            ? dueDates.filter((dueDate) => dueDate.getTime() <= today.getTime()).length
            : 0;
        renderHistoricalLatePicker(dueDates, paidCount, firstPaidAtDelivery);
        historicalPaidInput.max = String(Math.min(count || 0, dueCount));
        const additionalHistoricalPayments = Math.max(
            paidCount - (firstPaidAtDelivery ? 1 : 0),
            0
        );
        historicalMethodInput.disabled = additionalHistoricalPayments < 1;
        historicalMethodInput.required = additionalHistoricalPayments > 0;

        const inconsistentFirstInstallment = firstPendingAtDelivery && paidCount > 0;
        historicalSummary.classList.toggle(
            "is-warning",
            paidCount > dueCount || inconsistentFirstInstallment
        );
        historicalSummary.classList.toggle(
            "is-active",
            (paidCount > 0 || firstPaidAtDelivery) &&
                paidCount <= dueCount &&
                !inconsistentFirstInstallment
        );
        if (inconsistentFirstInstallment) {
            historicalSummary.textContent =
                "La cantidad de cuotas ya pagadas comienza por la cuota 1, pero arriba figura como pendiente.";
        } else if (paidCount < 1 && firstPaidAtDelivery) {
            historicalSummary.textContent =
                "La cuota 1 se registrará desde la entrega. No se agregarán otros pagos anteriores.";
        } else if (paidCount < 1) {
            historicalSummary.textContent =
                "No se marcarán cuotas anteriores como pagadas.";
        } else if (paidCount > dueCount) {
            const dueLabel = dueCount === 1 ? "1 cuota" : `${dueCount} cuotas`;
            historicalSummary.textContent = `Hasta hoy vencieron ${dueLabel}. Revisá la cantidad indicada.`;
        } else {
            const pendingCount = Math.max((count || 0) - paidCount, 0);
            const lateCount = selectedLateInstallments().length;
            const onTimeCount = Math.max(paidCount - lateCount, 0);
            const paidLabel = paidCount === 1
                ? "1 cuota quedará pagada"
                : `${paidCount} cuotas quedarán pagadas`;
            const pendingLabel = pendingCount === 1 ? "1 cuota conservará" : `${pendingCount} cuotas conservarán`;
            historicalSummary.textContent =
                `${paidLabel}: ${onTimeCount} en fecha y ${lateCount} con atraso. ` +
                `${pendingLabel} su estado pendiente o futuro.`;
        }
    }

    function updateDeliveryInstallmentSummary(installmentAmountCents) {
        if (!deliveryInstallmentSummary || !sameDayFirstDueInput?.checked) return;
        const status = deliveryInstallmentStatus();
        deliveryInstallmentSummary.classList.toggle("is-paid", status === "paid");
        deliveryInstallmentSummary.classList.toggle("is-pending", status === "pending");
        if (status === "paid") {
            const amountText = installmentAmountCents > 0
                ? ` por ${currency.format(installmentAmountCents / 100)}`
                : "";
            deliveryInstallmentSummary.textContent =
                `Se registrará la cuota 1${amountText} como pagada en la fecha de entrega. ` +
                "El pago inicial aparte, si existe, se guardará como un movimiento separado.";
        } else if (status === "pending") {
            deliveryInstallmentSummary.textContent =
                "La cuota 1 aparecerá pendiente en Cobranza el día de la entrega. " +
                "Si no se paga, tendrá recargo desde el día siguiente.";
        } else {
            deliveryInstallmentSummary.textContent =
                "Elegí si la cuota 1 fue pagada o quedó pendiente.";
        }
    }

    function moneyInputValue(cents) {
        return cents > 0 ? (cents / 100).toFixed(2).replace(".", ",") : "";
    }

    function updateInstallmentCalculationNote() {
        if (!installmentCalculationNote) return;
        const installmentCents = parseMoneyToCents(installmentAmountInput?.value);
        const count = Number.parseInt(countInput?.value, 10) || 0;
        if (!installmentCents || !count) {
            installmentCalculationNote.textContent =
                isLoan()
                    ? "Si lo completás, cantidad de cuotas × monto de cada cuota calculará el total a devolver."
                    : "Si lo completás, cantidad de cuotas × monto de cada cuota calculará el precio automáticamente.";
            return;
        }
        const totalCents = installmentCents * count;
        const downPaymentCents = parseMoneyToCents(downPaymentInput?.value);
        if (customInstallmentTotalInput.checked || isLoan()) {
            installmentCalculationNote.textContent =
                `${count} cuotas × ${currency.format(installmentCents / 100)} = ` +
                `${currency.format(totalCents / 100)} ${isLoan() ? "a devolver" : "en cuotas"}.`;
            return;
        }
        const productPriceCents = totalCents + downPaymentCents;
        const initialText = downPaymentCents
            ? ` + ${currency.format(downPaymentCents / 100)} de pago inicial`
            : "";
        installmentCalculationNote.textContent =
            `${count} cuotas × ${currency.format(installmentCents / 100)}` +
            `${initialText} = precio ${currency.format(productPriceCents / 100)}.`;
    }

    function applyInstallmentAmountCalculation() {
        const installmentCents = parseMoneyToCents(installmentAmountInput?.value);
        const count = Number.parseInt(countInput?.value, 10) || 0;
        updateInstallmentCalculationNote();
        if (!installmentCents || !count) {
            synchronizeFinancing();
            return;
        }

        const totalCents = installmentCents * count;
        const downPaymentCents = parseMoneyToCents(downPaymentInput.value);
        applyingInstallmentCalculation = true;
        try {
            financedInput.value = moneyInputValue(totalCents);
            if (isLoan()) {
                const principalCents = parseMoneyToCents(productPriceInput.value);
                if (principalCents > 0 && loanInterestRateInput) {
                    const rate = ((totalCents - principalCents) * 100) / principalCents;
                    loanInterestRateInput.value = Math.max(rate, 0)
                        .toFixed(2)
                        .replace(".", ",");
                }
                updatePreview();
                return;
            }
            if (!customInstallmentTotalInput.checked) {
                productPriceInput.value = moneyInputValue(
                    totalCents + downPaymentCents
                );
            }
            synchronizeFinancing();
        } finally {
            applyingInstallmentCalculation = false;
        }
    }

    function clearInstallmentAmountCalculation() {
        if (applyingInstallmentCalculation || !installmentAmountInput?.value) return;
        installmentAmountInput.value = "";
        updateInstallmentCalculationNote();
    }

    function updatePreview() {
        const productPriceCents = parseMoneyToCents(productPriceInput.value);
        const downPaymentCents = isLoan() ? 0 : parseMoneyToCents(downPaymentInput.value);
        const totalCents = parseMoneyToCents(financedInput.value);
        const baseBalanceCents = Math.max(productPriceCents - downPaymentCents, 0);
        const operationTotalCents = isLoan() ? totalCents : downPaymentCents + totalCents;
        const adjustmentCents = operationTotalCents - productPriceCents;
        const count = Number.parseInt(countInput.value, 10);
        const firstDate = dateFromIso(firstDueInput.value);
        const isMonthly = frequencyInput.value === "monthly";
        const interval = frequencyInput.value === "biweekly" ? 14 : 7;
        const frequencyLabel =
            frequencyInput.options[frequencyInput.selectedIndex]?.text || "Sin datos";
        const estimatedInstallmentCents = totalCents && count > 0
            ? Math.floor(totalCents / count)
            : 0;

        updateHistoricalSummary(firstDate, frequencyInput.value, count);
        updateDeliveryInstallmentSummary(estimatedInstallmentCents);

        totalOutput.textContent = currency.format(totalCents / 100);
        productPriceOutput.textContent = currency.format(productPriceCents / 100);
        downPaymentOutput.textContent = currency.format(downPaymentCents / 100);
        baseBalanceOutput.textContent = currency.format(baseBalanceCents / 100);
        operationTotalOutput.textContent = currency.format(operationTotalCents / 100);
        adjustmentOutput.textContent = currency.format(Math.abs(adjustmentCents) / 100);
        adjustmentLabel.textContent = isLoan()
            ? "Interés total"
            : adjustmentCents > 0
              ? "Costo de financiación"
              : adjustmentCents < 0
                ? "Descuento en cuotas"
                : "Ajuste por financiación";
        frequencyOutput.textContent = frequencyLabel;

        if (!totalCents || !count || count < 1 || !firstDate) {
            captionOutput.textContent =
                "Completá el total, la cantidad y el vencimiento de la cuota 1.";
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
            const historicalPaidCount = Number.parseInt(
                historicalPaidInput?.value,
                10
            ) || 0;
            const paidAtDelivery =
                Boolean(sameDayFirstDueInput?.checked) &&
                deliveryInstallmentStatus() === "paid";
            const previewPaidCount = Math.max(
                historicalPaidCount,
                paidAtDelivery ? 1 : 0
            );
            if (number <= previewPaidCount) {
                numberCell.textContent += " ✓";
                row.classList.add("is-historical-paid");
                const lateDays = Number.parseInt(historicalLateState[number], 10) || 0;
                if (lateDays > 0) {
                    numberCell.textContent += ` +${lateDays}d`;
                    row.classList.add("is-historical-late");
                }
            }
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
        const downPaymentCents = isLoan() ? 0 : parseMoneyToCents(downPaymentInput.value);
        const interestRate = parseLocalizedNumber(loanInterestRateInput?.value);
        const suggestedCents = isLoan()
            ? Math.round(productPriceCents * (1 + interestRate / 100))
            : Math.max(productPriceCents - downPaymentCents, 0);
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
            ? isLoan()
                ? "Total acordado manualmente. El interés efectivo se guardará según ese importe."
                : "Total elegido: no se recalcula al modificar el precio o el pago inicial aparte."
            : isLoan()
                ? "Cálculo automático: dinero prestado más el interés total indicado."
                : "Cálculo automático: precio del producto menos pago inicial aparte.";

        const hasDownPayment = downPaymentCents > 0;
        downPaymentMethodInput.disabled = !hasDownPayment;
        downPaymentMethodInput.required = hasDownPayment;
        if (!hasDownPayment) downPaymentMethodInput.value = "";
        if (loanInterestRateInput) {
            loanInterestRateInput.readOnly = isLoan() && usesCustomTotal;
            loanInterestRateInput.classList.toggle("is-calculated", isLoan() && usesCustomTotal);
            if (isLoan() && usesCustomTotal && productPriceCents > 0) {
                const totalCents = parseMoneyToCents(financedInput.value);
                if (totalCents >= productPriceCents) {
                    const effectiveRate = ((totalCents - productPriceCents) * 100) / productPriceCents;
                    loanInterestRateInput.value = effectiveRate.toFixed(2).replace(".", ",");
                }
            }
        }
        updatePreview();
    }

    function updateProductDescription() {
        if (isLoan()) {
            const current = descriptionInput.value.trim();
            if (!current || current === lastAutomaticDescription) {
                descriptionInput.value = "Préstamo de dinero";
                lastAutomaticDescription = descriptionInput.value;
            }
            return;
        }
        const selectedText =
            productInput.options[productInput.selectedIndex]?.text?.trim() || "";
        const selectedProductName = selectedText.split(" · ", 1)[0];
        const current = descriptionInput.value.trim();
        if (!current || current === lastAutomaticDescription) {
            descriptionInput.value = selectedText.startsWith("Seleccionar")
                ? ""
                : selectedProductName;
            lastAutomaticDescription = descriptionInput.value;
        }
    }

    function synchronizeOperationType() {
        const loan = isLoan();
        productOnlyElements.forEach((element) => { element.hidden = loan; });
        loanOnlyElements.forEach((element) => { element.hidden = !loan; });
        if (productInput) productInput.required = !loan;
        if (loanDisbursementMethodInput) {
            loanDisbursementMethodInput.required = loan;
            loanDisbursementMethodInput.disabled = !loan;
        }
        if (loanInterestRateInput) loanInterestRateInput.disabled = !loan;

        cashPriceLabel.textContent = loan ? "Dinero prestado" : "Precio del producto";
        financedAmountLabel.textContent = loan ? "Total a devolver" : "Total en cuotas";
        operationDescriptionLabel.textContent = loan
            ? "Detalle o motivo del préstamo (opcional)"
            : "Descripción en esta venta";
        customTotalLabel.textContent = loan
            ? "Usar otro total a devolver"
            : "Usar otro total en cuotas";
        customTotalHelp.textContent = loan
            ? "Activá esta opción si acordaste directamente un importe final, en lugar de un porcentaje."
            : "Solo activalo si el total acordado será distinto de precio menos pago inicial aparte.";
        deliveryDateLabel.textContent = loan
            ? "Fecha en que se entregó el dinero"
            : "Fecha de entrega";
        sameDayDueLabel.textContent = loan
            ? "La cuota 1 vence el día en que se entrega el dinero"
            : "La cuota 1 vence el día de la entrega";
        if (firstInstallmentPaidLabel) {
            const input = firstInstallmentPaidLabel.querySelector("input");
            const text = loan
                ? "Pagó la cuota 1 al recibir el dinero"
                : "Pagó la cuota 1 al recibir el producto";
            firstInstallmentPaidLabel.replaceChildren();
            if (input) firstInstallmentPaidLabel.append(input, document.createTextNode(` ${text}`));
        }
        previewTotalLabel.textContent = loan ? "Total a devolver" : "Total en cuotas";
        previewPriceLabel.textContent = loan ? "Capital prestado" : "Precio del producto";
        previewOperationTotalLabel.textContent = loan
            ? "Total final a devolver"
            : "Total final de la venta";
        productPriceInput.placeholder = loan ? "Ej. 300000" : "Ej. 400000";
        descriptionInput.placeholder = loan
            ? "Ej. Préstamo personal"
            : "Se completa con el producto seleccionado";
        if (loan) {
            downPaymentInput.value = "";
            downPaymentMethodInput.value = "";
        }
        updateInstallmentCalculationNote();
        updateProductDescription();
        if (installmentAmountInput?.value) applyInstallmentAmountCalculation();
        else synchronizeFinancing();
    }

    function synchronizeSameDayFirstDue() {
        const sameDay = Boolean(sameDayFirstDueInput?.checked);
        if (sameDay && deliveryDateInput?.value) {
            firstDueInput.value = deliveryDateInput.value;
        }
        firstDueInput.readOnly = sameDay;
        firstDueInput.setAttribute("aria-readonly", String(sameDay));
        firstDueInput.classList.toggle("is-calculated", sameDay);
        if (deliveryInstallmentPanel) deliveryInstallmentPanel.hidden = !sameDay;
        synchronizeDeliveryInstallmentStatus();
    }

    function synchronizeDeliveryInstallmentStatus() {
        const paid =
            Boolean(sameDayFirstDueInput?.checked) &&
            deliveryInstallmentStatus() === "paid";
        if (deliveryInstallmentMethodWrap) {
            deliveryInstallmentMethodWrap.hidden = !paid;
        }
        if (deliveryInstallmentMethodInput) {
            deliveryInstallmentMethodInput.disabled = !paid;
            deliveryInstallmentMethodInput.required = paid;
            if (!paid) deliveryInstallmentMethodInput.value = "";
        }
        updatePreview();
    }

    function normalizeSearchText(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLocaleLowerCase("es-AR")
            .trim();
    }

    function saveSaleDraft() {
        const draft = {};
        Array.from(form.elements).forEach((control) => {
            if (!control.name || control.name === "csrfmiddlewaretoken") return;
            if (control.type === "radio") {
                if (control.checked) draft[control.name] = control.value;
                return;
            }
            if (control.type === "checkbox") {
                draft[control.name] = control.checked;
                return;
            }
            draft[control.name] = control.value;
        });
        try {
            sessionStorage.setItem(saleDraftKey, JSON.stringify(draft));
        } catch (_error) {
            // La venta sigue siendo utilizable aunque el navegador no permita guardar.
        }
    }

    function restoreSaleDraft() {
        const params = new URLSearchParams(window.location.search);
        if (params.get("restaurar") !== "1") return;
        let draft = null;
        try {
            draft = JSON.parse(sessionStorage.getItem(saleDraftKey) || "null");
            sessionStorage.removeItem(saleDraftKey);
        } catch (_error) {
            draft = null;
        }
        if (!draft || typeof draft !== "object") return;

        Object.entries(draft).forEach(([name, value]) => {
            if (name === "customer" && params.has("cliente")) return;
            if (name === "product" && params.has("producto")) return;
            const controls = Array.from(form.elements).filter(
                (control) => control.name === name
            );
            controls.forEach((control) => {
                if (control.type === "radio") {
                    control.checked = control.value === value;
                } else if (control.type === "checkbox") {
                    control.checked = Boolean(value);
                } else {
                    control.value = String(value ?? "");
                }
            });
        });
    }

    function setupSelectSearch(searchInput) {
        const select = document.querySelector(searchInput.dataset.selectSearch || "");
        if (!select) return;
        const box = searchInput.closest(".select-search-box");
        const counter = document.querySelector(
            `[data-select-search-count="${searchInput.dataset.selectSearch}"]`
        );
        const label = searchInput.dataset.selectLabel || "registro";
        const options = Array.from(select.options)
            .filter((option) => option.value)
            .map((option) => ({
                value: option.value,
                text: option.textContent.trim(),
                disabled: option.disabled,
            }));
        const results = document.createElement("div");
        let visibleOptions = [];
        let activeIndex = -1;

        results.className = "select-search-results";
        results.id = `${select.id}-search-results`;
        results.setAttribute("role", "listbox");
        results.hidden = true;
        box?.append(results);
        searchInput.setAttribute("role", "combobox");
        searchInput.setAttribute("aria-controls", results.id);
        select.hidden = true;
        select.setAttribute("aria-hidden", "true");
        select.tabIndex = -1;

        function closeResults() {
            results.hidden = true;
            searchInput.setAttribute("aria-expanded", "false");
            searchInput.removeAttribute("aria-activedescendant");
            activeIndex = -1;
        }

        function chooseOption(option) {
            select.value = option.value;
            searchInput.value = option.text;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            if (counter) counter.textContent = `${label[0].toUpperCase()}${label.slice(1)} seleccionado`;
            closeResults();
            searchInput.focus();
        }

        function setActiveOption(index) {
            if (!visibleOptions.length) return;
            activeIndex = (index + visibleOptions.length) % visibleOptions.length;
            Array.from(results.querySelectorAll("button")).forEach((button, position) => {
                const isActive = position === activeIndex;
                button.classList.toggle("is-active", isActive);
                if (isActive) searchInput.setAttribute("aria-activedescendant", button.id);
            });
        }

        function renderOptions(showAll = false) {
            const query = showAll ? "" : normalizeSearchText(searchInput.value);
            visibleOptions = options.filter(
                (option) => !option.disabled && normalizeSearchText(option.text).includes(query)
            );
            results.replaceChildren();
            visibleOptions.forEach((option, index) => {
                const button = document.createElement("button");
                button.type = "button";
                button.id = `${results.id}-${index}`;
                button.className = "select-search-result";
                button.setAttribute("role", "option");
                button.setAttribute("aria-selected", String(option.value === select.value));
                button.textContent = option.text;
                button.addEventListener("pointerdown", (event) => event.preventDefault());
                button.addEventListener("click", () => chooseOption(option));
                results.append(button);
            });
            if (!visibleOptions.length) {
                const empty = document.createElement("p");
                empty.className = "select-search-empty";
                empty.textContent = `No se encontró ningún ${label}.`;
                results.append(empty);
            }
            results.hidden = false;
            searchInput.setAttribute("aria-expanded", "true");
            activeIndex = -1;
            if (counter) {
                counter.textContent = query
                    ? `${visibleOptions.length} coincidencia${visibleOptions.length === 1 ? "" : "s"}`
                    : `${visibleOptions.length} disponible${visibleOptions.length === 1 ? "" : "s"}`;
            }
        }

        searchInput.addEventListener("focus", () => {
            searchInput.select();
            renderOptions(true);
        });
        searchInput.addEventListener("click", () => renderOptions(true));
        searchInput.addEventListener("input", () => {
            const selected = options.find((option) => option.value === select.value);
            if (!selected || searchInput.value !== selected.text) select.value = "";
            renderOptions();
        });
        searchInput.addEventListener("search", () => {
            if (!searchInput.value) select.value = "";
            renderOptions();
        });
        searchInput.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                if (results.hidden) renderOptions(true);
                setActiveOption(activeIndex + (event.key === "ArrowDown" ? 1 : -1));
            } else if (event.key === "Enter" && activeIndex >= 0) {
                event.preventDefault();
                chooseOption(visibleOptions[activeIndex]);
            } else if (event.key === "Escape") {
                closeResults();
            }
        });
        document.addEventListener("pointerdown", (event) => {
            if (!box?.contains(event.target)) closeResults();
        });

        const selected = options.find((option) => option.value === select.value);
        if (selected) {
            searchInput.value = selected.text;
            if (counter) counter.textContent = `${label[0].toUpperCase()}${label.slice(1)} seleccionado`;
        } else if (counter) {
            counter.textContent = `${options.length} disponible${options.length === 1 ? "" : "s"}`;
        }
    }

    [frequencyInput, firstDueInput].forEach((control) => {
        control?.addEventListener("input", updatePreview);
        control?.addEventListener("change", updatePreview);
    });
    countInput?.addEventListener("input", () => {
        if (installmentAmountInput?.value) applyInstallmentAmountCalculation();
        else updatePreview();
    });
    countInput?.addEventListener("change", () => {
        if (installmentAmountInput?.value) applyInstallmentAmountCalculation();
        else updatePreview();
    });
    financedInput?.addEventListener("input", () => {
        if (isLoan() && customInstallmentTotalInput?.checked) synchronizeFinancing();
        else updatePreview();
    });
    financedInput?.addEventListener("change", () => {
        if (isLoan() && customInstallmentTotalInput?.checked) synchronizeFinancing();
        else updatePreview();
    });
    productPriceInput?.addEventListener("input", () => {
        clearInstallmentAmountCalculation();
        synchronizeFinancing();
    });
    productPriceInput?.addEventListener("change", () => {
        clearInstallmentAmountCalculation();
        synchronizeFinancing();
    });
    downPaymentInput?.addEventListener("input", () => {
        if (installmentAmountInput?.value) applyInstallmentAmountCalculation();
        else synchronizeFinancing();
    });
    downPaymentInput?.addEventListener("change", () => {
        if (installmentAmountInput?.value) applyInstallmentAmountCalculation();
        else synchronizeFinancing();
    });
    loanInterestRateInput?.addEventListener("input", () => {
        clearInstallmentAmountCalculation();
        synchronizeFinancing();
    });
    loanInterestRateInput?.addEventListener("change", synchronizeFinancing);
    installmentAmountInput?.addEventListener("input", applyInstallmentAmountCalculation);
    installmentAmountInput?.addEventListener("change", applyInstallmentAmountCalculation);
    customInstallmentTotalInput?.addEventListener("change", () => {
        if (installmentAmountInput?.value) applyInstallmentAmountCalculation();
        else synchronizeFinancing();
    });
    productInput?.addEventListener("change", updateProductDescription);
    operationTypeInputs.forEach((control) => {
        control.addEventListener("change", synchronizeOperationType);
    });
    deliveryDateInput?.addEventListener("input", () => {
        if (sameDayFirstDueInput?.checked) synchronizeSameDayFirstDue();
    });
    deliveryDateInput?.addEventListener("change", () => {
        if (sameDayFirstDueInput?.checked) synchronizeSameDayFirstDue();
    });
    sameDayFirstDueInput?.addEventListener("change", synchronizeSameDayFirstDue);
    deliveryInstallmentStatusInputs.forEach((control) => {
        control.addEventListener("change", synchronizeDeliveryInstallmentStatus);
    });
    historicalPaidInput?.addEventListener("input", updatePreview);
    historicalPaidInput?.addEventListener("change", updatePreview);
    saleDraftLinks.forEach((link) => link.addEventListener("click", saveSaleDraft));
    restoreSaleDraft();
    document.querySelectorAll("[data-select-search]").forEach(setupSelectSearch);

    form.addEventListener("submit", () => {
        // This is synchronous: the latest visible values are copied before the
        // browser builds the POST request. The server recalculates them again.
        synchronizeSameDayFirstDue();
        if (installmentAmountInput?.value) applyInstallmentAmountCalculation();
        else synchronizeFinancing();
        if (submitButton && form.checkValidity()) {
            submitButton.disabled = true;
            submitButton.textContent = "Guardando venta…";
        }
    });

    synchronizeSameDayFirstDue();
    synchronizeOperationType();
})();
