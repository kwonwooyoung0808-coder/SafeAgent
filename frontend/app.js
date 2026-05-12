const releaseData = {
  channel: "stable"
};

const MANIFEST_PATH = "./downloads/safeagent-release-manifest.json";
const BUNDLE_PATH = "./downloads/safeagent-deployment-bundle.zip";

const installModeLabels = {
  "docker-compose": "Docker Compose"
};

const priorityLabels = {
  Recommended: "권장",
  Critical: "긴급",
  Optional: "선택"
};

const statusLabels = {
  Ready: "준비 완료",
  Completed: "완료",
  Failed: "실패",
  Pending: "대기 중"
};

function formatKoreanDateTime(date = new Date()) {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date) + " KST";
}

function formatManifestDate(value) {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return formatKoreanDateTime(parsed);
}

function getArtifactPath(manifest, kind, fallbackPath) {
  const artifact = (manifest.artifacts || []).find((item) => item.kind === kind);
  if (!artifact || !artifact.path) {
    return fallbackPath;
  }
  return artifact.path;
}

function setListItems(container, items) {
  if (!container) {
    return;
  }

  container.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    container.appendChild(li);
  });
}

function setSummaryItems(container, notes, version) {
  if (!container) {
    return;
  }

  container.innerHTML = "";
  notes.forEach((note, index) => {
    const item = document.createElement("div");
    item.className = "summary-item";

    const tag = document.createElement("span");
    tag.className = "summary-tag";
    tag.textContent = index === 0 ? version : `항목 ${index + 1}`;

    const text = document.createElement("p");
    text.textContent = note;

    item.appendChild(tag);
    item.appendChild(text);
    container.appendChild(item);
  });
}

function setHistoryRows(container, history) {
  if (!container) {
    return;
  }

  const header = container.querySelector(".history-head");
  container.innerHTML = "";
  if (header) {
    container.appendChild(header);
  }

  history.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "history-row";

    const date = document.createElement("span");
    date.textContent = formatManifestDate(entry.at);

    const version = document.createElement("span");
    version.textContent = entry.version;

    const action = document.createElement("span");
    action.textContent = entry.action;

    const status = document.createElement("span");
    const normalizedStatus = entry.status || "";
    status.textContent = statusLabels[normalizedStatus] || normalizedStatus;
    if (normalizedStatus.toLowerCase() === "ready" || normalizedStatus.toLowerCase() === "completed") {
      status.className = "ok";
    }

    row.appendChild(date);
    row.appendChild(version);
    row.appendChild(action);
    row.appendChild(status);
    container.appendChild(row);
  });
}

async function loadReleaseManifest() {
  const staticResponse = await fetch(MANIFEST_PATH, {
    cache: "no-store"
  });
  if (!staticResponse.ok) {
    throw new Error(`manifest fetch failed: ${staticResponse.status}`);
  }
  return staticResponse.json();
}

async function hydrateReleaseData() {
  const currentVersionCardEl = document.getElementById("current-version-card");
  const latestVersionCardEl = document.getElementById("latest-version-card");
  const currentDetailsEl = document.getElementById("current-details");
  const latestDetailsEl = document.getElementById("latest-details");
  const summaryListEl = document.getElementById("summary-list");
  const historyTableEl = document.getElementById("history-table");

  try {
    const manifest = await loadReleaseManifest();
    const latestVersion = `v${manifest.latest_version}`;
    const currentVersion = `v${manifest.current_version}`;

    currentVersionEl.textContent = currentVersion;
    currentVersionCardEl.textContent = currentVersion;
    channelNameEl.textContent = manifest.channel || releaseData.channel;
    lastCheckedEl.textContent = formatKoreanDateTime();
    latestVersionCardEl.textContent = latestVersion;

    setListItems(currentDetailsEl, [
      `배포 채널: ${manifest.channel || releaseData.channel}`,
      `배포 형식: ${installModeLabels[manifest.recommended_install_mode] || manifest.recommended_install_mode || "Docker Compose"}`,
      "운영 모델: 회사별 독립 서버"
    ]);

    setListItems(latestDetailsEl, [
      `배포일: ${formatManifestDate(manifest.published_at)}`,
      `중요도: ${priorityLabels[manifest.priority] || manifest.priority || "권장"}`,
      `DB 마이그레이션: ${manifest.requires_migration ? "필요" : "없음"}`
    ]);

    setSummaryItems(summaryListEl, manifest.notes || [], latestVersion);
    setHistoryRows(historyTableEl, manifest.history || []);

    if (bundleDownloadEl) {
      bundleDownloadEl.href = getArtifactPath(
        manifest,
        "deployment-bundle",
        BUNDLE_PATH
      );
    }

    return latestVersion;
  } catch (error) {
    console.error(error);
    return "v0.2.0";
  }
}

const currentVersionEl = document.getElementById("current-version");
const channelNameEl = document.getElementById("channel-name");
const lastCheckedEl = document.getElementById("last-checked");
const refreshButton = document.getElementById("refresh-release");
const bundleDownloadEl = document.getElementById("bundle-download");

if (currentVersionEl) {
  currentVersionEl.textContent = "v0.1.0";
}

if (channelNameEl) {
  channelNameEl.textContent = releaseData.channel;
}

if (lastCheckedEl) {
  lastCheckedEl.textContent = formatKoreanDateTime();
}

if (refreshButton) {
  refreshButton.addEventListener("click", async () => {
    const latestVersion = await hydrateReleaseData();
    refreshButton.textContent = `${latestVersion} 확인됨`;
    window.setTimeout(() => {
      refreshButton.textContent = "최신 버전 확인";
    }, 1800);
  });
}

if (bundleDownloadEl) {
  bundleDownloadEl.href = BUNDLE_PATH;
}

hydrateReleaseData();
