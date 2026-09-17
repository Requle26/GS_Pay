const scanButton = document.querySelector("#scan-button");
const scanStatus = document.querySelector("#scan-status");
const balanceValue = document.querySelector("#balance-value");
const resultMessage = document.querySelector("#result-message");
const studentIdentity = document.querySelector("#student-identity");
const studentName = document.querySelector("#student-name");
const studentNumber = document.querySelector("#student-number");
const transactionSection = document.querySelector("#transaction-section");
const transactionList = document.querySelector("#transaction-list");
const transactionEmpty = document.querySelector("#transaction-empty");

const SCAN_TIMEOUT_MS = 30_000;

function setScanning(isScanning) {
  scanButton.disabled = isScanning;
  scanButton.querySelector("span").textContent = isScanning
    ? "학생증 인식 중..."
    : "학생증 인식하기";
}

function showNotFound(message = "정보를 찾을 수 없습니다.") {
  balanceValue.textContent = "-";
  resultMessage.textContent = message;
  resultMessage.hidden = false;
  studentIdentity.hidden = true;
  transactionSection.hidden = true;
  transactionList.replaceChildren();
}

async function getCardInfo(serialNumber) {
  const response = await fetch(
    `/api/cards/${encodeURIComponent(serialNumber)}`,
  );
  const data = await response.json();
  return { response, data };
}

async function getTransactions(serialNumber) {
  const response = await fetch(
    `/api/cards/${encodeURIComponent(serialNumber)}/transactions`,
  );
  if (!response.ok) throw new Error("이용 내역을 불러오지 못했습니다.");
  const data = await response.json();
  return data.transactions || [];
}

function formatTransactionAmount(transaction) {
  const amount = Number(transaction.amount || 0);
  const isSpend = transaction.type === "SPEND";
  const signedAmount = isSpend && amount > 0 ? -amount : amount;
  const sign = signedAmount > 0 ? "+" : "";
  return `${sign}${signedAmount.toLocaleString("ko-KR")}원`;
}

function formatTransactionType(type) {
  return (
    {
      CHARGE: "입금",
      SPEND: "출금",
      ADJUSTMENT: "잔액 조정",
    }[type] || type
  );
}

function formatTransactionDate(value) {
  if (!value) return "시간 정보 없음";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function showTransactions(transactions) {
  transactionList.replaceChildren();
  transactionSection.hidden = false;
  transactionEmpty.hidden = transactions.length > 0;
  transactions.forEach((transaction) => {
    const item = document.createElement("article");
    item.className = "transaction-item";

    const details = document.createElement("div");
    details.className = "transaction-details";
    const type = document.createElement("strong");
    type.textContent = formatTransactionType(transaction.type);
    const description = document.createElement("span");
    description.textContent = transaction.description || "거래 내역";
    const date = document.createElement("time");
    date.dateTime = transaction.created_at || "";
    date.textContent = formatTransactionDate(transaction.created_at);
    details.append(type, description, date);

    const amount = document.createElement("strong");
    amount.className = `transaction-amount transaction-${String(transaction.type).toLowerCase()}`;
    amount.textContent = formatTransactionAmount(transaction);
    item.append(details, amount);
    transactionList.append(item);
  });
}

function showStudentIdentity(card) {
  studentName.textContent = card.name || "이름 정보 없음";
  studentNumber.textContent = `학번 ${card.student_number || "-"}`;
  studentIdentity.hidden = false;
}

async function scanStudentCard() {
  resultMessage.hidden = true;
  scanStatus.textContent = "30초 안에 학생증을 NFC 리더기에 가까이 대주세요.";
  setScanning(true);

  if (!("NDEFReader" in window)) {
    showNotFound("이 기기에서는 NFC를 사용할 수 없습니다.");
    scanStatus.textContent =
      "NFC를 지원하는 기기와 브라우저에서 다시 시도해주세요.";
    setScanning(false);
    return;
  }

  const controller = new AbortController();
  let scanFinished = false;
  const finishScan = () => {
    if (scanFinished) return;
    scanFinished = true;
    controller.abort();
    window.clearTimeout(timeoutId);
    setScanning(false);
  };
  const timeoutId = window.setTimeout(() => {
    finishScan();
    showNotFound("학생증을 읽지 못했습니다.");
    scanStatus.textContent = "인식 시간이 종료되었습니다. 다시 시도해주세요.";
  }, SCAN_TIMEOUT_MS);

  try {
    const reader = new NDEFReader();
    await reader.scan({ signal: controller.signal });
    reader.addEventListener(
      "reading",
      async (event) => {
        finishScan();
        scanStatus.textContent = "학생증 정보를 확인하는 중입니다...";

        try {
          const card = await getCardInfo(event.serialNumber);
          if (!card.response.ok) {
            if (
              card.response.headers.get("X-Card-Status") === "SUSPEND" ||
              card.data.detail === "이용 정지된 학생증입니다."
            ) {
              showNotFound("이용 정지된 학생증입니다.");
              scanStatus.textContent = "이 학생증은 현재 사용할 수 없습니다.";
              return;
            }

            showNotFound();
            scanStatus.textContent = "등록되지 않은 학생증입니다.";
            return;
          }

          balanceValue.textContent = `${Number(card.data.balance).toLocaleString("ko-KR")}원`;
          showStudentIdentity(card.data);
          resultMessage.hidden = true;
          try {
            const transactions = await getTransactions(event.serialNumber);
            showTransactions(transactions);
          } catch (error) {
            transactionSection.hidden = true;
          }
          scanStatus.textContent = "학생증을 인식했습니다.";
        } catch (error) {
          showNotFound();
          scanStatus.textContent = "잔액 정보를 불러오지 못했습니다.";
        }
      },
      { once: true },
    );
    reader.addEventListener(
      "readingerror",
      () => {
        finishScan();
        showNotFound("학생증을 읽지 못했습니다.");
        scanStatus.textContent = "학생증을 다시 인식해주세요.";
      },
      { once: true },
    );
  } catch (error) {
    if (!scanFinished) {
      finishScan();
      showNotFound("학생증 인식을 시작하지 못했습니다.");
      scanStatus.textContent = "NFC 권한을 허용한 뒤 다시 시도해주세요.";
    }
  }
}

scanButton.addEventListener("click", scanStudentCard);
