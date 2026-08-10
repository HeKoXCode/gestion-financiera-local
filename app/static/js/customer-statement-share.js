(() => {
    "use strict";

    function setStatus(button, message) {
        const container = button.closest(".profile-action-stack, .print-toolbar") || document;
        const output = container.querySelector("[data-share-status]");
        if (output) {
            output.textContent = message;
        }
    }

    function downloadBlob(blob, filename) {
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = objectUrl;
        link.download = filename;
        link.hidden = true;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    }

    async function shareStatement(button) {
        const originalText = button.textContent;
        const pdfUrl = button.dataset.pdfUrl;
        const whatsappUrl = button.dataset.whatsappUrl;
        const filename = button.dataset.filename || "resumen-de-cuenta.pdf";
        const title = button.dataset.shareTitle || "Resumen de cuenta";
        const shareText = button.dataset.shareText || "Te comparto tu resumen de cuenta.";

        button.disabled = true;
        button.textContent = "Preparando PDF…";
        setStatus(button, "Generando el archivo para compartir…");

        try {
            const response = await fetch(pdfUrl, {
                credentials: "same-origin",
                cache: "no-store",
            });
            if (!response.ok) {
                throw new Error(`No se pudo generar el PDF (${response.status}).`);
            }

            const blob = await response.blob();
            const file =
                typeof File === "function"
                    ? new File([blob], filename, { type: "application/pdf" })
                    : null;
            const canShareFile = Boolean(
                file &&
                    navigator.share &&
                    navigator.canShare &&
                    navigator.canShare({ files: [file] })
            );

            if (canShareFile) {
                try {
                    await navigator.share({
                        files: [file],
                        title,
                        text: shareText,
                    });
                    setStatus(button, "Resumen compartido.");
                    return;
                } catch (shareError) {
                    if (shareError && shareError.name === "AbortError") {
                        setStatus(button, "No se compartió el resumen.");
                        return;
                    }
                    // Si el menú del celular no acepta el archivo, continúa con la descarga.
                }
            }

            downloadBlob(blob, filename);
            setStatus(
                button,
                "El PDF quedó guardado. En WhatsApp, adjuntalo desde Descargas."
            );
            const whatsappWindow = window.open(whatsappUrl, "_blank");
            if (whatsappWindow) {
                whatsappWindow.opener = null;
            } else {
                window.location.assign(whatsappUrl);
            }
        } catch (error) {
            setStatus(button, "No se pudo preparar el PDF. Probá con Guardar resumen PDF.");
        } finally {
            button.disabled = false;
            button.textContent = originalText;
        }
    }

    document.querySelectorAll("[data-statement-share]").forEach((button) => {
        button.addEventListener("click", () => shareStatement(button));
    });

    document.querySelectorAll("[data-print-statement]").forEach((button) => {
        button.addEventListener("click", () => window.print());
    });

    if (document.body.dataset.autoPrint === "true") {
        window.addEventListener("load", () => window.print(), { once: true });
    }
})();
