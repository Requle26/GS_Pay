const overviewRefreshButton = document.querySelector("#overview-refresh-button");
const overviewStatus = document.querySelector("#overview-status");
const boothAddButton = document.querySelector("#booth-add-button");
const boothCancelButton = document.querySelector("#booth-cancel-button");
const boothForm = document.querySelector("#booth-form");
const boothIdInput = document.querySelector("#booth-id");
const boothNameInput = document.querySelector("#booth-name");
const boothStatusField = document.querySelector("#booth-status-field");
const boothStatusInput = document.querySelector("#booth-status");
const boothFormStatus = document.querySelector("#booth-form-status");
const boothTableBody = document.querySelector("#booth-table-body");
const boothEmpty = document.querySelector("#booth-empty");
const accountAddButton = document.querySelector("#account-add-button");
const accountCancelButton = document.querySelector("#account-cancel-button");
const accountForm = document.querySelector("#account-form");
const accountIdInput = document.querySelector("#account-id");
const accountEmailField = document.querySelector("#account-email-field");
const accountPasswordField = document.querySelector("#account-password-field");
const accountEmailInput = document.querySelector("#account-email");
const accountPasswordInput = document.querySelector("#account-password");
const accountUsernameInput = document.querySelector("#account-username");
const accountRoleInput = document.querySelector("#account-role");
const accountBoothField = document.querySelector("#account-booth-field");
const accountBoothInput = document.querySelector("#account-booth-id");
const accountStatusField = document.querySelector("#account-status-field");
const accountStatusInput = document.querySelector("#account-status");
const accountFormStatus = document.querySelector("#account-form-status");
const accountTableBody = document.querySelector("#account-table-body");
const accountEmpty = document.querySelector("#account-empty");
const transactionTableBody = document.querySelector("#transaction-table-body");
const transactionEmpty = document.querySelector("#transaction-empty");
const transactionCountLabel = document.querySelector("#transaction-count-label");

let booths = Array.isArray(window.adminBooths) ? [...window.adminBooths] : [];
let accounts = Array.isArray(window.adminAccounts)
  ? [...window.adminAccounts]
  : [];
let stats = window.adminStats || {};
let transactions = Array.isArray(window.adminTransactions)
  ? [...window.adminTransactions]
  : [];

function readJsonResponse(response) {
  return response
    .json()
    .catch(() => ({ detail: "서버 응답을 읽지 못했습니다." }));
}

function formatWon(value) {
  return `${Number(value || 0).toLocaleString("ko-KR")}원`;
}

function formatCount(value, suffix) {
  return `${Number(value || 0).toLocaleString("ko-KR")}${suffix}`;
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("ko-KR", {
        year: "numeric",
        month: "numeric",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function syncBoothOptions() {
  const previous = accountBoothInput.value;
  accountBoothInput.replaceChildren();
  const emptyOption = document.createElement("option");
  emptyOption.value = "";
  emptyOption.textContent = "선택 안 함";
  accountBoothInput.append(emptyOption);
  booths.forEach((booth) => {
    const option = document.createElement("option");
    option.value = booth.id;
    option.textContent = booth.name;
    accountBoothInput.append(option);
  });
  accountBoothInput.value = previous;
}

function updateRoleFields() {
  const needsBooth = accountRoleInput.value === "BOOTH";
  accountBoothField.hidden = false;
  accountBoothInput.required = needsBooth;
  if (!needsBooth) {
    accountBoothInput.value = "";
  }
}

function renderStats() {
  document.querySelector("#stat-student-count").textContent = formatCount(
    stats.student_count,
    "명",
  );
  document.querySelector("#stat-active-student-count").textContent = formatCount(
    stats.active_student_count,
    "명",
  );
  document.querySelector("#stat-total-balance").textContent = formatWon(
    stats.total_balance,
  );
  document.querySelector("#stat-total-charge").textContent = formatWon(
    stats.total_charge,
  );
  document.querySelector("#stat-total-spend").textContent = formatWon(
    stats.total_spend,
  );
  document.querySelector("#stat-counts").textContent =
    `${stats.booth_count || 0} / ${stats.admin_count || 0} / ${stats.transaction_count || 0}`;
}

function renderBooths() {
  boothTableBody.replaceChildren();
  boothEmpty.hidden = booths.length > 0;
  booths.forEach((booth) => {
    const row = document.createElement("tr");
    row.dataset.boothId = booth.id;
    const nameCell = document.createElement("td");
    nameCell.textContent = booth.name;
    const statusCell = document.createElement("td");
    statusCell.textContent = booth.status;
    const actionCell = document.createElement("td");
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "booth-secondary-button booth-edit-button";
    editButton.textContent = "수정";
    editButton.dataset.boothId = booth.id;
    editButton.dataset.boothName = booth.name;
    editButton.dataset.boothStatus = booth.status;
    actionCell.append(editButton);
    row.append(nameCell, statusCell, actionCell);
    boothTableBody.append(row);
  });
  syncBoothOptions();
}

function renderAccounts() {
  accountTableBody.replaceChildren();
  accountEmpty.hidden = accounts.length > 0;
  accounts.forEach((account) => {
    const row = document.createElement("tr");
    row.dataset.adminId = account.id;
    const cells = [
      account.username,
      account.role,
      account.booth_name || "-",
      account.status,
    ].map((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      return cell;
    });
    const actionCell = document.createElement("td");
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "booth-secondary-button account-edit-button";
    editButton.textContent = "수정";
    editButton.dataset.adminId = account.id;
    editButton.dataset.username = account.username;
    editButton.dataset.role = account.role;
    editButton.dataset.boothId = account.booth_id || "";
    editButton.dataset.status = account.status;
    actionCell.append(editButton);
    row.append(...cells, actionCell);
    accountTableBody.append(row);
  });
}

function renderTransactions() {
  transactionTableBody.replaceChildren();
  transactionEmpty.hidden = transactions.length > 0;
  transactionCountLabel.textContent = `최근 ${transactions.length}건`;
  transactions.forEach((tx) => {
    const row = document.createElement("tr");
    const values = [
      formatDate(tx.created_at),
      tx.type || "-",
      formatWon(tx.amount),
      tx.student_label || "-",
      tx.booth_name || "-",
      tx.admin_name || "-",
      tx.description || "-",
    ];
    values.forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    transactionTableBody.append(row);
  });
}

function applyOverview(data) {
  stats = data.stats || {};
  booths = data.booths || [];
  accounts = data.admins || [];
  transactions = data.transactions || [];
  renderStats();
  renderBooths();
  renderAccounts();
  renderTransactions();
}

async function refreshOverview(statusEl = overviewStatus) {
  statusEl.textContent = "데이터를 불러오는 중입니다...";
  overviewRefreshButton.disabled = true;
  try {
    const response = await fetch("/api/admin/overview");
    const result = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(result.detail || "데이터를 불러오지 못했습니다.");
    }
    applyOverview(result);
    statusEl.textContent = "최신 데이터로 갱신했습니다.";
  } catch (error) {
    statusEl.textContent = error.message;
  } finally {
    overviewRefreshButton.disabled = false;
  }
}

function resetBoothForm() {
  boothForm.reset();
  boothIdInput.value = "";
  boothStatusField.hidden = true;
  boothForm.hidden = true;
  boothFormStatus.textContent = "";
}

function openBoothForm(booth = null) {
  boothForm.hidden = false;
  boothFormStatus.textContent = "";
  boothIdInput.value = booth?.id || "";
  boothNameInput.value = booth?.name || "";
  boothStatusInput.value = booth?.status || "ACTIVE";
  boothStatusField.hidden = !booth;
  boothNameInput.focus();
}

function resetAccountForm() {
  accountForm.reset();
  accountIdInput.value = "";
  accountEmailField.hidden = false;
  accountPasswordField.hidden = false;
  accountEmailInput.required = true;
  accountPasswordInput.required = true;
  accountStatusField.hidden = true;
  accountForm.hidden = true;
  accountFormStatus.textContent = "";
  updateRoleFields();
}

function openAccountForm(account = null) {
  accountForm.hidden = false;
  accountFormStatus.textContent = "";
  accountIdInput.value = account?.id || "";
  accountUsernameInput.value = account?.username || "";
  accountRoleInput.value = account?.role || "EXCHANGE";
  accountBoothInput.value = account?.booth_id || "";
  accountStatusInput.value = account?.status || "ACTIVE";
  const editing = Boolean(account);
  accountEmailField.hidden = editing;
  accountPasswordField.hidden = editing;
  accountEmailInput.required = !editing;
  accountPasswordInput.required = !editing;
  accountStatusField.hidden = !editing;
  updateRoleFields();
  (editing ? accountUsernameInput : accountEmailInput).focus();
}

boothAddButton.addEventListener("click", () => openBoothForm());
boothCancelButton.addEventListener("click", resetBoothForm);
accountAddButton.addEventListener("click", () => openAccountForm());
accountCancelButton.addEventListener("click", resetAccountForm);
accountRoleInput.addEventListener("change", updateRoleFields);
overviewRefreshButton.addEventListener("click", () => refreshOverview());

boothTableBody.addEventListener("click", (event) => {
  const button = event.target.closest(".booth-edit-button");
  if (!button) return;
  openBoothForm({
    id: button.dataset.boothId,
    name: button.dataset.boothName,
    status: button.dataset.boothStatus,
  });
});

accountTableBody.addEventListener("click", (event) => {
  const button = event.target.closest(".account-edit-button");
  if (!button) return;
  openAccountForm({
    id: button.dataset.adminId,
    username: button.dataset.username,
    role: button.dataset.role,
    booth_id: button.dataset.boothId,
    status: button.dataset.status,
  });
});

boothForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const boothId = boothIdInput.value;
  const formData = new FormData();
  formData.set("name", boothNameInput.value.trim());
  if (boothId) {
    formData.set("status", boothStatusInput.value);
  }
  boothFormStatus.textContent = "저장 중...";
  try {
    const response = await fetch(
      boothId ? `/api/admin/booths/${boothId}` : "/api/admin/booths",
      { method: "POST", body: formData },
    );
    const result = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(result.detail || "부스를 저장하지 못했습니다.");
    }
    resetBoothForm();
    await refreshOverview(boothFormStatus);
    boothFormStatus.textContent = boothId
      ? "부스 정보를 수정했습니다."
      : "부스를 추가했습니다.";
  } catch (error) {
    boothFormStatus.textContent = error.message;
  }
});

accountForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const adminId = accountIdInput.value;
  const formData = new FormData();
  formData.set("username", accountUsernameInput.value.trim());
  formData.set("role", accountRoleInput.value);
  formData.set("booth_id", accountBoothInput.value);
  if (adminId) {
    formData.set("status", accountStatusInput.value);
  } else {
    formData.set("email", accountEmailInput.value.trim());
    formData.set("password", accountPasswordInput.value);
  }
  accountFormStatus.textContent = "저장 중...";
  try {
    const response = await fetch(
      adminId ? `/api/admin/accounts/${adminId}` : "/api/admin/accounts",
      { method: "POST", body: formData },
    );
    const result = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(result.detail || "계정을 저장하지 못했습니다.");
    }
    resetAccountForm();
    await refreshOverview(accountFormStatus);
    accountFormStatus.textContent = adminId
      ? "계정 정보를 수정했습니다."
      : "계정을 추가했습니다.";
  } catch (error) {
    accountFormStatus.textContent = error.message;
  }
});

renderStats();
renderBooths();
renderAccounts();
renderTransactions();
updateRoleFields();
