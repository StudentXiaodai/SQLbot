const STORAGE_KEY = "sqlbot.providerSettings";
const elements = {
  settingsForm: document.querySelector("#settings-form"),
  baseUrl: document.querySelector("#base-url"),
  model: document.querySelector("#model"),
  apiKey: document.querySelector("#api-key"),
  clearSettings: document.querySelector("#clear-settings"),
  toggleSettings: document.querySelector("#toggle-settings"),
  settingsMessage: document.querySelector("#settings-message"),
  questionForm: document.querySelector("#question-form"),
  question: document.querySelector("#question"),
  generateButton: document.querySelector("#generate-button"),
  sql: document.querySelector("#sql"),
  copySql: document.querySelector("#copy-sql"),
  executeButton: document.querySelector("#execute-button"),
  feedback: document.querySelector("#feedback"),
  results: document.querySelector("#results"),
  resultMeta: document.querySelector("#result-meta"),
  resultTable: document.querySelector("#result-table"),
};

function showFeedback(message, type = "info") {
  elements.feedback.hidden = false;
  elements.feedback.className = `feedback ${type}`;
  elements.feedback.textContent = message;
}

function clearFeedback() {
  elements.feedback.hidden = true;
  elements.feedback.textContent = "";
}

function providerFromForm() {
  return {
    base_url: elements.baseUrl.value.trim(),
    api_key: elements.apiKey.value.trim(),
    model: elements.model.value.trim(),
  };
}

function loadSettings() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return;
  try {
    const settings = JSON.parse(saved);
    elements.baseUrl.value = settings.baseUrl || elements.baseUrl.value;
    elements.apiKey.value = settings.apiKey || "";
    elements.model.value = settings.model || "";
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }
}

function setBusy(button, busy, label) {
  button.disabled = busy;
  button.dataset.originalLabel ||= button.textContent;
  button.textContent = busy ? label : button.dataset.originalLabel;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "请求失败，请稍后重试。");
  return data;
}

function renderResults(data) {
  elements.results.hidden = false;
  elements.resultTable.replaceChildren();
  const headerRow = document.createElement("tr");
  data.columns.forEach((column) => {
    const cell = document.createElement("th");
    cell.textContent = column;
    headerRow.append(cell);
  });
  const thead = document.createElement("thead");
  thead.append(headerRow);
  const tbody = document.createElement("tbody");
  data.rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((value) => {
      const td = document.createElement("td");
      td.textContent = value === null ? "NULL" : String(value);
      tr.append(td);
    });
    tbody.append(tr);
  });
  elements.resultTable.append(thead, tbody);
  elements.resultMeta.textContent = data.rows.length
    ? `返回 ${data.row_count} 行${data.truncated ? "（结果已截断为前 200 行）" : ""}`
    : "查询没有返回记录。";
}

elements.settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const provider = providerFromForm();
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    baseUrl: provider.base_url,
    apiKey: provider.api_key,
    model: provider.model,
  }));
  elements.settingsMessage.textContent = "设置已保存到当前浏览器。";
});

elements.clearSettings.addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  elements.apiKey.value = "";
  elements.model.value = "";
  elements.settingsMessage.textContent = "浏览器保存的设置已清除。";
});

elements.toggleSettings.addEventListener("click", () => {
  const collapsed = elements.settingsForm.hidden;
  elements.settingsForm.hidden = !collapsed;
  elements.toggleSettings.textContent = collapsed ? "收起" : "展开";
  elements.toggleSettings.setAttribute("aria-expanded", String(collapsed));
});

elements.questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFeedback();
  elements.results.hidden = true;
  const provider = providerFromForm();
  if (!provider.base_url || !provider.api_key || !provider.model) {
    showFeedback("请先填写并保存 Base URL、API Key 和模型名称。", "error");
    return;
  }
  setBusy(elements.generateButton, true, "正在生成…");
  try {
    const data = await requestJson("/api/generate-sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: elements.question.value.trim(), provider }),
    });
    elements.sql.value = data.sql;
    elements.executeButton.disabled = false;
    showFeedback(data.message, "success");
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setBusy(elements.generateButton, false);
  }
});

elements.executeButton.addEventListener("click", async () => {
  clearFeedback();
  const sql = elements.sql.value.trim();
  if (!sql) {
    showFeedback("请先生成或输入 SQL。", "error");
    return;
  }
  setBusy(elements.executeButton, true, "正在执行…");
  try {
    const data = await requestJson("/api/execute-sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql }),
    });
    renderResults(data);
    showFeedback("查询已执行。", "success");
  } catch (error) {
    showFeedback(error.message, "error");
  } finally {
    setBusy(elements.executeButton, false);
  }
});

elements.copySql.addEventListener("click", async () => {
  if (!elements.sql.value.trim()) {
    showFeedback("没有可复制的 SQL。", "error");
    return;
  }
  try {
    await navigator.clipboard.writeText(elements.sql.value);
    showFeedback("SQL 已复制到剪贴板。", "success");
  } catch {
    showFeedback("复制失败，请手动复制 SQL。", "error");
  }
});

loadSettings();
