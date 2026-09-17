const menuForm = document.querySelector("#menu-form");
const menuAddButton = document.querySelector("#menu-add-button");
const menuCancelButton = document.querySelector("#menu-cancel-button");
const menuIdInput = document.querySelector("#menu-id");
const menuNameInput = document.querySelector("#menu-name");
const menuPriceInput = document.querySelector("#menu-price");
const menuFormStatus = document.querySelector("#menu-form-status");
const menuList = document.querySelector("#menu-list");
const menuEmpty = document.querySelector("#menu-empty");
const paymentPanel = document.querySelector("#payment-panel");
const paymentCloseButton = document.querySelector("#payment-close-button");
const paymentMenuName = document.querySelector("#payment-menu-name");
const paymentScanButton = document.querySelector("#payment-scan-button");
const paymentStatus = document.querySelector("#payment-status");
const salesButton = document.querySelector("#sales-button");
const salesPanel = document.querySelector("#sales-panel");
const salesCloseButton = document.querySelector("#sales-close-button");
const salesTotal = document.querySelector("#sales-total");
const salesCount = document.querySelector("#sales-count");
const salesList = document.querySelector("#sales-list");
const salesEmpty = document.querySelector("#sales-empty");
const salesStatus = document.querySelector("#sales-status");

const SCAN_TIMEOUT_MS = 30_000;
let selectedMenu = null;

function readJsonResponse(response) {
  return response
    .json()
    .catch(() => ({ detail: "서버 응답을 읽지 못했습니다." }));
}

function formatSalesDate(value) {
  if (!value) return "시간 정보 없음";
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

function renderSales(transactions) {
  salesList.replaceChildren();
  salesEmpty.hidden = transactions.length > 0;
  transactions.forEach((transaction) => {
    const item = document.createElement("article");
    item.className = "sales-row";
    const detail = document.createElement("div");
    detail.className = "sales-detail";
    const description = document.createElement("strong");
    description.textContent = transaction.description || "메뉴 결제";
    const date = document.createElement("time");
    date.textContent = formatSalesDate(transaction.created_at);
    detail.append(description, date);
    const amount = document.createElement("strong");
    amount.className = "sales-amount";
    amount.textContent = `${Number(transaction.amount || 0).toLocaleString("ko-KR")}원`;
    item.append(detail, amount);
    salesList.append(item);
  });
}

async function loadSales() {
  salesPanel.hidden = false;
  salesStatus.textContent = "매출을 불러오는 중입니다...";
  salesButton.disabled = true;
  try {
    const response = await fetch("/api/booth/sales");
    const result = await readJsonResponse(response);
    if (!response.ok)
      throw new Error(result.detail || "매출을 불러오지 못했습니다.");
    salesTotal.textContent = `${Number(result.total_sales || 0).toLocaleString("ko-KR")}원`;
    salesCount.textContent = `${result.transaction_count || 0}건`;
    renderSales(result.transactions || []);
    salesStatus.textContent = "최근 결제 거래를 표시하고 있습니다.";
    salesPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    salesStatus.textContent = error.message;
  } finally {
    salesButton.disabled = false;
  }
}

function resetMenuForm() {
  menuForm.reset();
  menuIdInput.value = "";
  menuForm.hidden = true;
  menuFormStatus.textContent = "";
}

function openMenuForm(menu = null) {
  selectedMenu = menu;
  menuIdInput.value = menu?.id || "";
  menuNameInput.value = menu?.name || "";
  menuPriceInput.value = menu?.price || "";
  menuForm.hidden = false;
  menuFormStatus.textContent = "";
  menuNameInput.focus();
}

function updateEmptyMessage() {
  menuEmpty.hidden = menuList.children.length > 0;
}

function createMenuRow(menu) {
  const row = document.createElement("article");
  row.className = "menu-row";
  row.dataset.menuId = menu.id;

  const info = document.createElement("div");
  info.className = "menu-info";
  const name = document.createElement("h3");
  name.textContent = menu.name;
  const price = document.createElement("p");
  price.textContent = `${Number(menu.price).toLocaleString("ko-KR")}원`;
  info.append(name, price);

  const actions = document.createElement("div");
  actions.className = "menu-actions";
  const payButton = document.createElement("button");
  payButton.className = "menu-pay-button";
  payButton.type = "button";
  payButton.textContent = "NFC 결제";
  payButton.addEventListener("click", () => openPayment(menu));
  const editButton = document.createElement("button");
  editButton.className = "menu-edit-button";
  editButton.type = "button";
  editButton.textContent = "수정";
  editButton.addEventListener("click", () => openMenuForm(menu));
  const deleteButton = document.createElement("button");
  deleteButton.className = "menu-delete-button";
  deleteButton.type = "button";
  deleteButton.textContent = "삭제";
  deleteButton.addEventListener("click", () => deleteMenu(menu, row));
  actions.append(payButton, editButton, deleteButton);

  row.append(info, actions);
  return row;
}

function addMenuToList(menu) {
  const oldRow = menuList.querySelector(`[data-menu-id="${menu.id}"]`);
  const newRow = createMenuRow(menu);
  if (oldRow) oldRow.replaceWith(newRow);
  else menuList.append(newRow);
  updateEmptyMessage();
}

async function deleteMenu(menu, row) {
  if (!window.confirm(`${menu.name} 메뉴를 삭제하시겠습니까?`)) return;
  try {
    const response = await fetch(
      `/api/booth/menus/${encodeURIComponent(menu.id)}/delete`,
      { method: "POST" },
    );
    const result = await readJsonResponse(response);
    if (!response.ok) {
      throw new Error(result.detail || "메뉴를 삭제하지 못했습니다.");
    }
    row.remove();
    updateEmptyMessage();
    menuFormStatus.textContent = "메뉴가 삭제되었습니다.";
  } catch (error) {
    menuFormStatus.textContent = error.message;
  }
}

async function saveMenu(event) {
  event.preventDefault();
  const saveButton = menuForm.querySelector("#menu-save-button");
  saveButton.disabled = true;
  menuFormStatus.textContent = "저장 중입니다...";
  const formData = new FormData(menuForm);
  const menuId = menuIdInput.value;
  const url = menuId
    ? `/api/booth/menus/${encodeURIComponent(menuId)}`
    : "/api/booth/menus";

  try {
    const response = await fetch(url, { method: "POST", body: formData });
    const result = await readJsonResponse(response);
    if (!response.ok)
      throw new Error(result.detail || "메뉴를 저장하지 못했습니다.");
    addMenuToList(result.menu);
    resetMenuForm();
  } catch (error) {
    menuFormStatus.textContent = error.message;
  } finally {
    saveButton.disabled = false;
  }
}

function openPayment(menu) {
  selectedMenu = menu;
  paymentPanel.hidden = false;
  paymentMenuName.textContent = `${menu.name} · ${Number(menu.price).toLocaleString("ko-KR")}원`;
  paymentStatus.textContent = "학생증을 NFC 리더기에 가까이 대주세요.";
  paymentScanButton.disabled = false;
  paymentPanel.scrollIntoView({ behavior: "smooth", block: "center" });
}

function closePayment() {
  paymentPanel.hidden = true;
  selectedMenu = null;
}

function setPaymentScanning(isScanning) {
  paymentScanButton.disabled = isScanning;
  paymentScanButton.textContent = isScanning
    ? "학생증 인식 중..."
    : "학생증 인식하기";
}

async function payWithSerial(serialNumber) {
  const formData = new FormData();
  formData.append("nfc_serial", serialNumber);
  const response = await fetch(
    `/api/booth/menus/${encodeURIComponent(selectedMenu.id)}/pay`,
    {
      method: "POST",
      body: formData,
    },
  );
  const result = await readJsonResponse(response);
  if (!response.ok) throw new Error(result.detail || "결제하지 못했습니다.");
  paymentStatus.textContent = `${result.student.name || "학생"}님 결제가 완료되었습니다. 잔액: ${Number(result.student.balance).toLocaleString("ko-KR")}원`;
}

async function scanForPayment() {
  if (!selectedMenu) return;
  setPaymentScanning(true);
  paymentStatus.textContent =
    "30초 안에 학생증을 NFC 리더기에 가까이 대주세요.";
  if (!("NDEFReader" in window)) {
    paymentStatus.textContent = "이 기기에서는 NFC를 사용할 수 없습니다.";
    setPaymentScanning(false);
    return;
  }

  const controller = new AbortController();
  let finished = false;
  const finish = () => {
    if (finished) return;
    finished = true;
    controller.abort();
    window.clearTimeout(timeoutId);
    setPaymentScanning(false);
  };
  const timeoutId = window.setTimeout(() => {
    finish();
    paymentStatus.textContent = "학생증을 읽지 못했습니다. 다시 시도해주세요.";
  }, SCAN_TIMEOUT_MS);

  try {
    const reader = new NDEFReader();
    await reader.scan({ signal: controller.signal });
    reader.addEventListener(
      "reading",
      async (event) => {
        finish();
        paymentStatus.textContent = "결제 가능 여부를 확인하는 중입니다...";
        try {
          await payWithSerial(event.serialNumber);
        } catch (error) {
          paymentStatus.textContent = error.message;
        }
      },
      { once: true },
    );
    reader.addEventListener(
      "readingerror",
      () => {
        finish();
        paymentStatus.textContent =
          "학생증을 읽지 못했습니다. 다시 시도해주세요.";
      },
      { once: true },
    );
  } catch (error) {
    finish();
    paymentStatus.textContent = "NFC 권한을 허용한 뒤 다시 시도해주세요.";
  }
}

menuAddButton.addEventListener("click", () => openMenuForm());
menuCancelButton.addEventListener("click", resetMenuForm);
menuForm.addEventListener("submit", saveMenu);
paymentCloseButton.addEventListener("click", closePayment);
paymentScanButton.addEventListener("click", scanForPayment);
salesButton.addEventListener("click", loadSales);
salesCloseButton.addEventListener("click", () => {
  salesPanel.hidden = true;
});

document.querySelectorAll(".menu-row").forEach((row) => {
  const menu = (window.boothMenus || []).find(
    (item) => String(item.id) === row.dataset.menuId,
  );
  if (!menu) return;
  row
    .querySelector(".menu-pay-button")
    .addEventListener("click", () => openPayment(menu));
  row
    .querySelector(".menu-edit-button")
    .addEventListener("click", () => openMenuForm(menu));
  row
    .querySelector(".menu-delete-button")
    .addEventListener("click", () => deleteMenu(menu, row));
});
updateEmptyMessage();
