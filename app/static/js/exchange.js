const scanButton = document.querySelector("#exchange-scan-button");
const scanStatus = document.querySelector("#exchange-scan-status");
const existingStudent = document.querySelector("#existing-student");
const existingStudentFields = document.querySelector(
  "#existing-student-fields",
);
const profileForm = document.querySelector("#student-profile-form");
const studentNumberInput = document.querySelector("#student-number-input");
const studentNameInput = document.querySelector("#student-name-input");
const profileStatus = document.querySelector("#student-profile-status");
const registerForm = document.querySelector("#student-register-form");
const registerStatus = document.querySelector("#student-register-status");
const serialInput = document.querySelector("#student-nfc-serial");
const chargeForm = document.querySelector("#student-charge-form");
const chargeStatus = document.querySelector("#student-charge-status");
const balanceForm = document.querySelector("#student-balance-form");
const balanceInput = document.querySelector("#student-balance-input");
const balanceStatus = document.querySelector("#student-balance-status");
const suspendButton = document.querySelector("#student-suspend-button");
const unsuspendButton = document.querySelector("#student-unsuspend-button");
const suspendStatus = document.querySelector("#student-suspend-status");
const serialLookupForm = document.querySelector("#serial-lookup-form");
const serialNumberInput = document.querySelector("#serial-number-input");
const studentTableBody = document.querySelector("#student-table-body");
const studentCount = document.querySelector("#student-count");
const studentEmpty = document.querySelector("#student-empty");
const studentColumns = window.studentColumns || [];
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
  chargeForm.hidden = false;
  existingStudentFields.replaceChildren();
  registerStatus.textContent = "";
  profileStatus.textContent = "";
  chargeStatus.textContent = "";
  balanceStatus.textContent = "";
  suspendStatus.textContent = "";
  suspendButton.hidden = true;
  unsuspendButton.hidden = true;
}

function showStudent(student, canCharge = true) {
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
  chargeForm.hidden = !canCharge;
  balanceForm.hidden = !canCharge;
  profileForm.hidden = false;
  suspendButton.hidden = !canCharge;
  unsuspendButton.hidden = canCharge;
  studentNumberInput.value = student.student_number ?? "";
  studentNameInput.value = student.name ?? "";
  if (student.balance !== null && student.balance !== undefined) {
    balanceInput.value = student.balance;
  }
  existingStudent.hidden = false;
}

function updateStudentList(student) {
  const serialNumber = String(student.nfc_serial || "");
  let row = Array.from(studentTableBody.rows).find(
    (currentRow) => currentRow.dataset.studentSerial === serialNumber,
  );

  if (!row) {
    row = document.createElement("tr");
    row.dataset.studentSerial = serialNumber;
    studentTableBody.append(row);
  }

  row.replaceChildren(
    ...studentColumns.map((column) => {
      const cell = document.createElement("td");
      cell.textContent = student[column] ?? "-";
      return cell;
    }),
  );

  studentCount.textContent = `${studentTableBody.rows.length}명`;
  studentEmpty.hidden = studentTableBody.rows.length > 0;
}

async function checkStudent(serialNumber) {
  const response = await fetch(
    `/api/exchange/students/${encodeURIComponent(serialNumber)}`,
  );
  if (!response.ok) throw new Error("학생 정보를 확인하지 못했습니다.");
  return response.json();
}

async function handleStudentIdentifier(serialNumber) {
  const normalizedSerialNumber = serialNumber.trim();
  if (!normalizedSerialNumber) {
    scanStatus.textContent = "시리얼 번호를 입력해주세요.";
    return;
  }

  resetStudentResult();
  scannedSerialNumber = normalizedSerialNumber;
  serialInput.value = normalizedSerialNumber;
  scanStatus.textContent = "학생증 등록 여부를 확인하는 중입니다...";

  try {
    const result = await checkStudent(normalizedSerialNumber);
    if (result.exists) {
      showStudent(result.student, result.can_charge);
      scanStatus.textContent = result.can_charge
        ? "등록된 학생증입니다."
        : "정지된 학생증입니다. 충전할 수 없습니다.";
      return;
    }

    registerForm.hidden = false;
    scanStatus.textContent = "기본 정보를 입력한 뒤 저장해주세요.";
  } catch (error) {
    scanStatus.textContent = error.message;
  }
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

        await handleStudentIdentifier(event.serialNumber);
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
    const result = await readResponse(response);
    if (!response.ok) throw new Error(result.detail || "저장하지 못했습니다.");

    registerForm.hidden = true;
    showStudent(result.student);
    updateStudentList(result.student);
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
    const result = await readResponse(response);
    if (!response.ok) throw new Error(result.detail || "충전하지 못했습니다.");

    showStudent(result.student);
    updateStudentList(result.student);
    chargeForm.reset();
    chargeStatus.textContent = "충전이 완료되었습니다.";
    scanStatus.textContent = "학생증을 인식했습니다.";
  } catch (error) {
    chargeStatus.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

balanceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = balanceForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  balanceStatus.textContent = "수정 중입니다...";

  try {
    const response = await fetch(
      `/api/exchange/students/${encodeURIComponent(scannedSerialNumber)}/balance`,
      {
        method: "POST",
        body: new FormData(balanceForm),
      },
    );
    const result = await readResponse(response);
    if (!response.ok)
      throw new Error(result.detail || "잔액을 수정하지 못했습니다.");

    showStudent(result.student);
    updateStudentList(result.student);
    balanceStatus.textContent = "잔액이 수정되었습니다.";
    scanStatus.textContent = "학생증 정보를 갱신했습니다.";
  } catch (error) {
    balanceStatus.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = profileForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  profileStatus.textContent = "수정 중입니다...";

  try {
    const response = await fetch(
      `/api/exchange/students/${encodeURIComponent(scannedSerialNumber)}/profile`,
      {
        method: "POST",
        body: new FormData(profileForm),
      },
    );
    const result = await readResponse(response);
    if (!response.ok)
      throw new Error(result.detail || "학생 정보를 수정하지 못했습니다.");

    showStudent(result.student);
    updateStudentList(result.student);
    profileStatus.textContent = "학생 정보가 수정되었습니다.";
    scanStatus.textContent = "학생증 정보를 갱신했습니다.";
  } catch (error) {
    profileStatus.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

suspendButton.addEventListener("click", async () => {
  if (!window.confirm("이 학생증의 이용을 정지하시겠습니까?")) return;

  suspendButton.disabled = true;
  suspendStatus.textContent = "정지 처리 중입니다...";

  try {
    const response = await fetch(
      `/api/exchange/students/${encodeURIComponent(scannedSerialNumber)}/suspend`,
      { method: "POST" },
    );
    const result = await readResponse(response);
    if (!response.ok)
      throw new Error(result.detail || "이용 정지에 실패했습니다.");

    showStudent(result.student, false);
    updateStudentList(result.student);
    suspendStatus.textContent = "이용이 정지되었습니다.";
    scanStatus.textContent = "정지된 학생증입니다.";
  } catch (error) {
    suspendStatus.textContent = error.message;
    suspendButton.disabled = false;
  }
});

unsuspendButton.addEventListener("click", async () => {
  if (!window.confirm("이 학생증의 이용 정지를 해제하시겠습니까?")) return;

  unsuspendButton.disabled = true;
  suspendStatus.textContent = "정지 해제 처리 중입니다...";

  try {
    const response = await fetch(
      `/api/exchange/students/${encodeURIComponent(scannedSerialNumber)}/unsuspend`,
      { method: "POST" },
    );
    const result = await readResponse(response);
    if (!response.ok)
      throw new Error(result.detail || "이용 정지 해제에 실패했습니다.");

    showStudent(result.student, true);
    updateStudentList(result.student);
    suspendStatus.textContent = "이용 정지가 해제되었습니다.";
    scanStatus.textContent = "학생증을 다시 사용할 수 있습니다.";
  } catch (error) {
    suspendStatus.textContent = error.message;
    unsuspendButton.disabled = false;
  }
});

scanButton.addEventListener("click", scanStudentCard);

serialLookupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = serialLookupForm.querySelector("button[type='submit']");
  submitButton.disabled = true;
  await handleStudentIdentifier(serialNumberInput.value);
  submitButton.disabled = false;
});

async function readResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();

  const message = await response.text();
  return { detail: message || "서버에서 응답을 받지 못했습니다." };
}
