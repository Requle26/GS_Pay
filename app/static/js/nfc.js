const scanButton = document.querySelector("#scan-button");
const scanStatus = document.querySelector("#scan-status");
const balanceValue = document.querySelector("#balance-value");
const resultMessage = document.querySelector("#result-message");

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
}

async function getBalance(serialNumber) {
  const response = await fetch(`/api/cards/${encodeURIComponent(serialNumber)}`);
  if (!response.ok) return null;

  const data = await response.json();
  return data.balance;
}

async function scanStudentCard() {
  resultMessage.hidden = true;
  scanStatus.textContent = "30초 안에 학생증을 NFC 리더기에 가까이 대주세요.";
  setScanning(true);

  if (!("NDEFReader" in window)) {
    showNotFound("이 기기에서는 NFC를 사용할 수 없습니다.");
    scanStatus.textContent = "NFC를 지원하는 기기와 브라우저에서 다시 시도해주세요.";
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
    reader.addEventListener("reading", async (event) => {
      finishScan();
      scanStatus.textContent = "학생증 정보를 확인하는 중입니다...";

      try {
        const balance = await getBalance(event.serialNumber);
        if (balance === null) {
          showNotFound();
          scanStatus.textContent = "등록되지 않은 학생증입니다.";
          return;
        }

        balanceValue.textContent = `${Number(balance).toLocaleString("ko-KR")}원`;
        resultMessage.hidden = true;
        scanStatus.textContent = "학생증을 인식했습니다.";
      } catch (error) {
        showNotFound();
        scanStatus.textContent = "잔액 정보를 불러오지 못했습니다.";
      }
    }, { once: true });
    reader.addEventListener("readingerror", () => {
      finishScan();
      showNotFound("학생증을 읽지 못했습니다.");
      scanStatus.textContent = "학생증을 다시 인식해주세요.";
    }, { once: true });
  } catch (error) {
    if (!scanFinished) {
      finishScan();
      showNotFound("학생증 인식을 시작하지 못했습니다.");
      scanStatus.textContent = "NFC 권한을 허용한 뒤 다시 시도해주세요.";
    }
  }
}

scanButton.addEventListener("click", scanStudentCard);
