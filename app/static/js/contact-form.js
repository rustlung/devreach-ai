(function () {
  const API_ENDPOINT = "/api/contact";
  const form = document.querySelector("[data-endpoint]");

  if (!form) {
    return;
  }

  const resultBox = form.querySelector("[data-result]");
  const submitButton = form.querySelector('button[type="submit"]');
  const demoToggle = getField("demo_enabled");
  const demoFields = document.getElementById("contact-demo-fields");
  const fieldNames = ["name", "phone", "email", "comment", "demo_recipient_email", "demo_access_token"];

  setDemoFieldsEnabled(false);

  if (demoToggle) {
    demoToggle.addEventListener("change", function () {
      setDemoFieldsEnabled(demoToggle.checked);
    });
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearErrors();
    setLoading(true);
    const demoModeRequested = isDemoModeEnabled();

    try {
      const response = await fetch(form.dataset.endpoint || API_ENDPOINT, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(buildPayload()),
      });
      const payload = await parseResponseBody(response);
      handleResponse(response, payload, demoModeRequested);
    } catch (error) {
      showMessage("Не удалось связаться с сервером. Проверьте соединение и повторите попытку.", "error");
    } finally {
      setLoading(false);
    }
  });

  function buildPayload() {
    const payload = {
      name: getField("name").value.trim(),
      phone: getField("phone").value.trim(),
      email: getField("email").value.trim(),
      // Комментарий не нормализуем на фронтенде: backend должен сохранить внутреннее форматирование.
      comment: getField("comment").value,
      website: getField("website").value,
    };

    if (isDemoModeEnabled()) {
      payload.demo_recipient_email = getField("demo_recipient_email").value.trim();
      payload.demo_access_token = getField("demo_access_token").value.trim();
    }

    return payload;
  }

  async function parseResponseBody(response) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      return null;
    }

    try {
      return await response.json();
    } catch (error) {
      return null;
    }
  }

  function handleResponse(response, payload, demoModeRequested) {
    if (response.ok) {
      const successMessage = demoModeRequested
        ? "Обращение принято. Результат обработки отправлен на указанный email."
        : "Обращение принято.";
      showMessage(successMessage, "success");
      form.reset();
      setDemoFieldsEnabled(false);
      return;
    }

    if (response.status === 422) {
      showMessage("Проверьте заполненные данные.", "error");
      showFieldErrors(payload && payload.error ? payload.error.details : []);
      return;
    }

    if (response.status === 429) {
      const retryAfter = response.headers.get("Retry-After");
      const message = retryAfter
        ? `Слишком много обращений. Попробуйте повторить позже. Повтор через ${retryAfter} сек.`
        : "Слишком много обращений. Попробуйте повторить позже.";
      showMessage(message, "error", payload ? payload.request_id : null);
      return;
    }

    if (response.status === 403) {
      showMessage("Режим демонстрационной проверки недоступен. Проверьте код доступа.", "error", payload ? payload.request_id : null);
      return;
    }

    showMessage("Не удалось отправить обращение. Попробуйте повторить позже.", "error", payload ? payload.request_id : null);
  }

  function showFieldErrors(details) {
    details.forEach(function (detail) {
      const fieldName = extractFieldName(detail.loc);
      if (!fieldName || !fieldNames.includes(fieldName)) {
        return;
      }
      const field = getField(fieldName);
      const errorBox = document.getElementById(`${field.id}-error`);
      field.setAttribute("aria-invalid", "true");
      if (errorBox) {
        errorBox.textContent = detail.msg || "Поле заполнено некорректно";
      }
    });
  }

  function extractFieldName(location) {
    if (!Array.isArray(location)) {
      return null;
    }
    return location[location.length - 1];
  }

  function clearErrors() {
    fieldNames.forEach(function (fieldName) {
      const field = getField(fieldName);
      const errorBox = document.getElementById(`${field.id}-error`);
      field.removeAttribute("aria-invalid");
      if (errorBox) {
        errorBox.textContent = "";
      }
    });
    resultBox.textContent = "";
    resultBox.className = "form-result";
  }

  function showMessage(message, kind, requestId) {
    resultBox.textContent = "";
    const text = document.createElement("p");
    text.textContent = message;
    resultBox.appendChild(text);

    if (requestId) {
      const requestIdText = document.createElement("p");
      requestIdText.className = "request-id";
      requestIdText.textContent = `Идентификатор запроса: ${requestId}`;
      resultBox.appendChild(requestIdText);
    }

    resultBox.className = `form-result is-${kind}`;
  }

  function setLoading(isLoading) {
    submitButton.disabled = isLoading;
    submitButton.textContent = isLoading ? submitButton.dataset.loadingText : submitButton.dataset.submitText;
    fieldNames.concat("website", "demo_enabled").forEach(function (fieldName) {
      const field = getField(fieldName);
      if (!field) {
        return;
      }
      if (fieldName === "demo_recipient_email" || fieldName === "demo_access_token") {
        field.disabled = isLoading || !isDemoModeEnabled();
        return;
      }
      field.disabled = isLoading;
    });
  }

  function getField(name) {
    return form.elements.namedItem(name);
  }

  function isDemoModeEnabled() {
    return Boolean(demoToggle && demoToggle.checked);
  }

  function setDemoFieldsEnabled(enabled) {
    if (!demoToggle || !demoFields) {
      return;
    }

    demoToggle.setAttribute("aria-expanded", enabled ? "true" : "false");
    demoFields.hidden = !enabled;
    ["demo_recipient_email", "demo_access_token"].forEach(function (fieldName) {
      const field = getField(fieldName);
      field.disabled = !enabled;
      if (!enabled) {
        field.value = "";
        field.removeAttribute("aria-invalid");
        const errorBox = document.getElementById(`${field.id}-error`);
        if (errorBox) {
          errorBox.textContent = "";
        }
      }
    });
  }
})();
