// Принимает форму «Неточность?» с карты и создаёт GitHub Issue от имени
// сервисного токена — так пользователю не нужно логиниться в GitHub.
// Требует секрет GITHUB_TOKEN (fine-grained PAT, только Issues: Write на этот репозиторий).
const REPO = "AleshaRabotaet/rantakartta";
// Прод-сайт на GitHub Pages + сам Netlify-сайт (прод и deploy-preview/branch-деплои
// вида deploy-preview-30--rantakartta.netlify.app) — превью нужны, чтобы форму можно
// было проверить до мержа PR.
const ALLOWED_ORIGINS = [
  /^https:\/\/alesharabotaet\.github\.io$/,
  /^https:\/\/([a-z0-9-]+--)?rantakartta\.netlify\.app$/,
];
const MAX_MESSAGE_LENGTH = 1000;

function corsHeaders(origin) {
  const allowed = origin && ALLOWED_ORIGINS.some(re => re.test(origin));
  return {
    "Access-Control-Allow-Origin": allowed ? origin : "null",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
}

exports.handler = async (event) => {
  const CORS_HEADERS = corsHeaders(event.headers?.origin || event.headers?.Origin);

  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: CORS_HEADERS, body: "" };
  }
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, headers: CORS_HEADERS, body: "Method not allowed" };
  }

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return { statusCode: 400, headers: CORS_HEADERS, body: "Invalid JSON" };
  }

  if (payload.website) {
    // honeypot-поле, заполняют только боты — тихо отвечаем «ок», ничего не создавая
    return { statusCode: 200, headers: CORS_HEADERS, body: JSON.stringify({ ok: true }) };
  }

  const { id, title, url, lat, lon, message } = payload;
  if (typeof id !== "string" || !id || typeof title !== "string" || !title ||
      typeof message !== "string" || !message.trim()) {
    return { statusCode: 400, headers: CORS_HEADERS, body: "Missing required fields" };
  }
  if (message.length > MAX_MESSAGE_LENGTH) {
    return { statusCode: 400, headers: CORS_HEADERS, body: "Message too long" };
  }

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return { statusCode: 500, headers: CORS_HEADERS, body: "Server misconfigured" };
  }

  const issueTitle = `Неточность: ${title} (${id})`;
  const issueBody = [
    `Объект: ${id}`,
    `Название: ${title}`,
    `Ссылка у хозяина: ${url ?? "—"}`,
    `Координаты: ${lat ?? "—"}, ${lon ?? "—"}`,
    "",
    "Что не так:",
    message.trim(),
  ].join("\n");

  const res = await fetch(`https://api.github.com/repos/${REPO}/issues`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "rantakartta-report-form",
    },
    body: JSON.stringify({ title: issueTitle, body: issueBody, labels: ["data"] }),
  });

  if (!res.ok) {
    return { statusCode: 502, headers: CORS_HEADERS, body: "GitHub API error" };
  }

  const issue = await res.json();
  return {
    statusCode: 200,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    body: JSON.stringify({ html_url: issue.html_url }),
  };
};
