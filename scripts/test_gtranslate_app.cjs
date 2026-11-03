/* Isolated browser profile: no production script or real user preferences are changed. */
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("../app/node_modules/playwright");

async function main() {
  const output = path.resolve(
    __dirname,
    "../artifacts/translation-benchmark/gtranslate",
  );
  const browser = await chromium.launch({
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const report = { errors: [], failures: [], observations: [] };
  page.on("pageerror", (error) => report.errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400)
      report.failures.push({
        url: response.url().split("?")[0],
        status: response.status(),
      });
  });
  try {
    await page.goto(
      "http://127.0.0.1:4174/anthrion-signal/?view=all&market=DE",
    );
    await page.locator(".row-title").first().waitFor();
    const first = page.locator("[data-signal-id]").first();
    const firstId = await first.getAttribute("data-signal-id");
    const title = await first.locator(".row-title").innerText();
    await page.evaluate(() => {
      const host = document.createElement("div");
      host.className = "gtranslate_wrapper";
      host.style.cssText =
        "position:fixed;bottom:0;right:0;z-index:100000;background:white";
      document.body.appendChild(host);
      window.gtranslateSettings = {
        default_language: "de",
        languages: ["en", "de", "it", "es"],
        wrapper_selector: ".gtranslate_wrapper",
      };
    });
    await page.addScriptTag({
      url: "https://cdn.gtranslate.net/widgets/latest/dropdown.js",
    });
    await page.locator(".gt_selector").focus();
    await page.waitForFunction(() => window.__GT?.translator, undefined, {
      timeout: 25000,
    });
    await page.locator(".gt_selector").selectOption("de|en");
    await page.waitForFunction(
      (text) => document.querySelector(".row-title").textContent !== text,
      title,
      { timeout: 25000 },
    );
    await page.waitForTimeout(1500);
    report.observations.push({
      step: "translated German market",
      original: title,
      visible: await first.locator(".row-title").innerText(),
    });
    await first.locator("input[type=checkbox]").click();
    await page.waitForTimeout(1000);
    report.observations.push({
      step: "hide after translation",
      hidden: await page.evaluate(() =>
        JSON.parse(localStorage.getItem("anthrion-hidden-v1")),
      ),
      firstId,
      rendered: await page.locator(".row-title").count(),
    });
    await page.locator(".row-select").first().click();
    report.observations.push({
      step: "select another record",
      heading: await page.locator(".inspector-heading h2").innerText(),
    });
    await page.locator(".signal-feed").evaluate((el) => {
      el.scrollTop = el.scrollHeight;
    });
    await page.waitForTimeout(2500);
    report.observations.push({
      step: "virtual scroll",
      titles: await page.locator(".row-title").allInnerTexts(),
      rendered: await page.locator(".row-title").count(),
    });
    await page.getByRole("button", { name: /^Sort opportunities:/ }).click();
    await page
      .getByRole("menuitemcheckbox", { name: "Show hidden", exact: true })
      .click();
    await page.waitForTimeout(1000);
    await page
      .locator(`[data-signal-id="${firstId}"] input[type=checkbox]`)
      .click();
    await page.waitForTimeout(500);
    report.observations.push({
      step: "unhide after translation",
      hidden: await page.evaluate(() =>
        JSON.parse(localStorage.getItem("anthrion-hidden-v1")),
      ),
      bodyPresent: await page.locator("#main").count(),
    });
    await page.screenshot({
      path: path.join(output, "app-test.png"),
      fullPage: true,
    });
  } catch (error) {
    report.error = String(error);
  } finally {
    fs.writeFileSync(
      path.join(output, "app-ready-results.json"),
      JSON.stringify(report, null, 2),
    );
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
  }
}
main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
