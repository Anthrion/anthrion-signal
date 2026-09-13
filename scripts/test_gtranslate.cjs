/* Internal-only evaluation under GTranslate's testing terms; never bundled into the app. */
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("../app/node_modules/playwright");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "artifacts/translation-benchmark/gtranslate");
fs.mkdirSync(output, { recursive: true });
const corpus = fs
  .readFileSync(
    path.join(root, "artifacts/translation-benchmark/float32/results.jsonl"),
    "utf8",
  )
  .trim()
  .split("\n")
  .map((line) => JSON.parse(line));
const languages = [...new Set(corpus.map((row) => row.language))];
const samples = languages.flatMap((language) =>
  corpus.filter((row) => row.language === language).slice(0, 3),
);
const html = (
  source,
  rows,
) => `<!doctype html><html lang="${source}"><meta charset="utf-8">
<title>Internal translation evaluation</title>
<style>body{font:16px/1.6 system-ui;max-width:1000px;margin:30px auto;padding:20px}article{border-top:1px solid #bbb;padding:10px 0}</style>
<h1 class="notranslate">Internal translation evaluation</h1><nav>Saved opportunities | Filters | Most recent</nav>
<div class="gtranslate_wrapper"></div><main id="records"></main>
<script>
const samples=${JSON.stringify(rows).replaceAll("<", "\\u003c")};
function add(row, index) {
 const article=document.createElement('article'); article.id='sample-'+index;
 article.lang=row.language==='nb'?'no':row.language; article.textContent=row.source;
 document.querySelector('#records').appendChild(article);
}
samples.forEach(add);
window.gtranslateSettings={default_language:${JSON.stringify(source)},languages:['en','de','el','da','fi','it','es','sv','no','is'],wrapper_selector:'.gtranslate_wrapper'};
</script><script src="https://cdn.gtranslate.net/widgets/latest/dropdown.js" defer></script></html>`;

async function main() {
  const server = http.createServer((req, res) => {
    const source =
      new URL(req.url, "http://localhost").searchParams.get("source") || "en";
    const rows =
      source === "en"
        ? samples
        : samples.filter(
            (row) => (row.language === "nb" ? "no" : row.language) === source,
          );
    res.setHeader("content-type", "text/html; charset=utf-8");
    res.end(html(source, rows));
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
  });
  const results = [];
  try {
    for (const source of [
      "en",
      ...languages.map((code) => (code === "nb" ? "no" : code)),
    ]) {
      const context = await browser.newContext();
      const page = await context.newPage();
      const errors = [],
        requests = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("requestfailed", (request) =>
        errors.push(
          `${request.url().split("?")[0]}: ${request.failure()?.errorText}`,
        ),
      );
      page.on("response", (response) => {
        const url = new URL(response.url());
        if (url.hostname !== "127.0.0.1")
          requests.push({
            host: url.hostname,
            path: url.pathname,
            status: response.status(),
          });
      });
      await page.goto(
        `http://127.0.0.1:${server.address().port}/?source=${source}`,
        { waitUntil: "domcontentloaded" },
      );
      await page.locator(".gt_selector").waitFor({ timeout: 30000 });
      const before = await page.locator("article").allTextContents();
      await page.locator(".gt_selector").selectOption(`${source}|en`);
      let changed = false;
      try {
        await page.waitForFunction(
          (text) => document.querySelector("article").textContent !== text,
          before[0],
          { timeout: 20000 },
        );
        changed = true;
        await page.waitForTimeout(2000);
      } catch {}
      const after = await page.locator("article").allTextContents();
      const result = {
        source,
        target: "en",
        changed,
        before,
        after,
        errors,
        requests,
      };
      results.push(result);
      fs.writeFileSync(
        path.join(output, "results.json"),
        JSON.stringify(results, null, 2),
      );
      console.log(
        JSON.stringify({
          source,
          changed,
          characters: before.join("").length,
          errors,
          requests,
        }),
      );
      await page.screenshot({
        path: path.join(output, `${source}.png`),
        fullPage: true,
      });
      await context.close();
      if (requests.some((item) => item.status === 429)) break;
    }
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
