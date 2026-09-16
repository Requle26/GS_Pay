const scanButton = document.querySelector("#exchange-scan-button");
const scanStatus = document.querySelector("#exchange-scan-status");
const existingStudent = document.querySelector("#existing-student");
const existingStudentFields = document.querySelector(
  "#existing-student-fields",
);
const registerForm = document.querySelector("#student-register-form");
const registerStatus = document.querySelector("#student-register-status");
const serialInput = document.querySelector("#student-nfc-serial");
const chargeForm = document.querySelector("#student-charge-form");
const chargeStatus = document.querySelector("#student-charge-status");
let scannedSerialNumber = "";

const SCAN_TIMEOUT_MS = 30_000;
const FIELD_LABELS = {
  nfc_serial: "NFC",
  student_number: "학번",
  name: "이름",
  balance: "잔액",
  status: "상태",
};

function setScanning(isScanning) {
  scanButton.disabled = isScanning;
  scanButton.querySelector("span").textContent = isScanning
    ? "학생증 인식 중..."
    : "학생증 인식하기";
}

function resetStudentResult() {
  existingStudent.hidden = true;
  registerForm.hidden = true;
  existingStudentFields.replaceChildren();
  registerStatus.textContent = "";
  chargeStatus.textContent = "";
}

function showStudent(student) {
  existingStudentFields.replaceChildren();
  Object.entries(student).forEach(([column, value]) => {
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = FIELD_LABELS[column] || column;
    detail.textContent =
      column === "balance" && value !== null && value !== undefined
        ? `${Number(value).toLocaleString("ko-KR")}원`
        : (value ?? "-");
    existingStudentFields.append(term, detail);
  });
  existingStudent.hidden = false;
}

async function checkStudent(serialNumber) {
  const response = await fetch(
    `/api/exchange/students/${encodeURIComponent(serialNumber)}`,
  );
  if (!response.ok) throw new Error("학생 정보를 확인하지 못했습니다.");
  return response.json();
}

async function scanStudentCard() {
  resetStudentResult();
  scanStatus.textContent = "30초 안에 학생증을 NFC 리더기에 가까이 대주세요.";
  setScanning(true);

  if (!("NDEFReader" in window)) {
    scanStatus.textContent = "이 기기에서는 NFC를 사용할 수 없습니다.";
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
    scanStatus.textContent = "학생증을 읽지 못했습니다. 다시 시도해주세요.";
  }, SCAN_TIMEOUT_MS);

  try {
    const reader = new NDEFReader();
    await reader.scan({ signal: controller.signal });
    reader.addEventListener(
      "reading",
      async (event) => {
        finishScan();
        scanStatus.textContent = "학생증 등록 여부를 확인하는 중입니다...";

        try {
          const result = await checkStudent(event.serialNumber);
          scannedSerialNumber = event.serialNumber;
          if (result.exists) {
            showStudent(result.student);
            scanStatus.textContent = "등록된 학생증입니다.";
            return;
          }

          serialInput.value = event.serialNumber;
          registerForm.hidden = false;
          scanStatus.textContent = "기본 정보를 입력한 뒤 저장해주세요.";
        } catch (error) {
          scanStatus.textContent = error.message;
        }
      },
      { once: true },
    );
    reader.addEventListener(
      "readingerror",
      () => {
        finishScan();
        scanStatus.textContent = "학생증을 읽지 못했습니다. 다시 인식해주세요.";
      },
      { once: true },
    );
  } catch (error) {
    if (!scanFinished) {
      finishScan();
      scanStatus.textContent = "NFC 권한을 허용한 뒤 다시 시도해주세요.";
    }
  }
}

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = registerForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  registerStatus.textContent = "저장 중입니다...";

  try {
    const response = await fetch("/api/exchange/students", {
      method: "POST",
      body: new FormData(registerForm),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "저장하지 못했습니다.");

    registerForm.hidden = true;
    showStudent(result.student);
    scanStatus.textContent = "학생 정보가 저장되었습니다.";
  } catch (error) {
    registerStatus.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

chargeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = chargeForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  chargeStatus.textContent = "충전 중입니다...";

  try {
    const response = await fetch(
      `/api/exchange/students/${encodeURIComponent(scannedSerialNumber)}/charge`,
      {
        method: "POST",
        body: new FormData(chargeForm),
      },
    );
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "충전하지 못했습니다.");

    showStudent(result.student);
    chargeForm.reset();
    chargeStatus.textContent = "충전이 완료되었습니다.";
    scanStatus.textContent = "학생증을 인식했습니다.";
  } catch (error) {
    chargeStatus.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

scanButton.addEventListener("click", scanStudentCard);
