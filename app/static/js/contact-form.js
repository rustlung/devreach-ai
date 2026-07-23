(function () {
  const API_ENDPOINT = "/api/contact";
  const form = document.querySelector("[data-endpoint]");

  if (!form) {
    return;
  }

  const resultBox = form.querySelector("[data-result]");
  const submitButton = form.querySelector('button[type="submit"]');
  const fieldNames = ["name", "phone", "email", "comment"];

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearErrors();
    setLoading(true);

    try {
      const response = await fetch(form.dataset.endpoint || API_ENDPOINT, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(buildPayload()),
      });
      const payload = await parseResponseBody(response);
      handleResponse(response, payload);
    } catch (error) {
      showMessage("Не удалось связаться с сервером. Проверьте соединение и повторите попытку.", "error");
    } finally {
      setLoading(false);
    }
  });

  function buildPayload() {
    return {
      name: getField("name").value.trim(),
      phone: getField("phone").value.trim(),
      email: getField("email").value.trim(),
      // Комментарий не нормализуем на фронтенде: backend должен сохранить внутреннее форматирование.
      comment: getField("comment").value,
      website: getField("website").value,
    };
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

  function handleResponse(response, payload) {
    if (response.ok) {
      showMessage("Обращение принято", "success");
      form.reset();
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
    fieldNames.concat("website").forEach(function (fieldName) {
      getField(fieldName).disabled = isLoading;
    });
  }

  function getField(name) {
    return form.elements.namedItem(name);
  }
})();
