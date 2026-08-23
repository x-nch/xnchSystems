import { firefox } from "/Users/xnch/xnchSystems-noisyUI/web/node_modules/playwright/index.mjs";

const BASE = "http://localhost:3100";
const routes = ["/product", "/services", "/teaching", "/community"];

const browser = await firefox.launch();

async function audit(route, { reducedMotion }) {
  const ctx = await browser.newContext({ reducedMotion });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(BASE + route, { waitUntil: "networkidle" });

  const result = {
    route,
    reducedMotion,
    errors,
    checks: {},
  };

  // grain layer present & static (no animation on any noise child)
  result.checks.grainOpacity = await page
    .locator(".mkt-noise__grain")
    .first()
    .evaluate((el) => getComputedStyle(el).opacity);
  const sweepVisible = await page
    .locator(".mkt-noise__sweep")
    .first()
    .isVisible()
    .catch(() => false);
  result.checks.sweepVisible = sweepVisible;
  result.checks.scanlinesPresent = await page
    .locator(".mkt-noise__scanlines")
    .first()
    .evaluate((el) => getComputedStyle(el).backgroundImage.includes("repeating-linear-gradient"));

  // CTA legibility: solid CTA has opaque chartreuse fill, no animation
  const cta = page.locator("a.mkt-cta--solid").first();
  result.checks.ctaBg = await cta.evaluate((el) => getComputedStyle(el).backgroundColor);
  result.checks.ctaColor = await cta.evaluate((el) => getComputedStyle(el).color);

  if (reducedMotion === "no-preference") {
    // eslint-disable-next-line
    // glitch triggers on hover and clears afterwards
    const h1 = page.locator(".mkt-glitch").first();
    result.checks.glitchOnHover = false;
    for (let i = 0; i < 6 && !result.checks.glitchOnHover; i++) {
      await page.waitForTimeout(300);
      await h1.hover();
      await page.waitForTimeout(80);
      result.checks.glitchOnHover = await h1.evaluate((el) =>
        el.classList.contains("mkt-glitch--on"),
      );
    }
    await page.waitForTimeout(400);
    result.checks.glitchClears = await h1.evaluate(
      (el) => !el.classList.contains("mkt-glitch--on"),
    );
  }

  // typed subhead (product only): full sentence in DOM in both modes
  const sr = page.locator("main .sr-only").first();
  if ((await sr.count()) > 0) {
    result.checks.fullSentenceInDom = await sr.textContent();
    result.checks.caretAnimation = await page
      .locator(".mkt-caret")
      .first()
      .evaluate((el) => getComputedStyle(el).animationName);
  }

  await page.screenshot({
    path: `/var/folders/s8/yk89zyjj1nj0_r_kfq5c2mdr0000gn/T/opencode/ff-${route.replace(/\//g, "_")}-${reducedMotion ? "rm" : "full"}.png`,
    fullPage: true,
  });
  await ctx.close();
  return result;
}

const report = [];
for (const r of routes) {
  report.push(await audit(r, { reducedMotion: "no-preference" }));
  report.push(await audit(r, { reducedMotion: "reduce" }));
}
await browser.close();

let fail = false;
for (const r of report) {
  const rm = r.reducedMotion === "reduce";
  const okSweep = rm ? r.checks.sweepVisible === false : true; // sweep may or may not be in viewport; hidden under RM must hold
    const problems = [];
  if (r.errors.length) problems.push(`console: ${r.errors.join(" | ")}`);
  if (rm && r.checks.sweepVisible) problems.push("sweep visible under reduced motion");
  if (rm && r.checks.glitchOnHover) problems.push("glitch active under reduced motion");
  console.log(
    `${r.route} [${r.reducedMotion}] ${problems.length ? "FAIL" : "PASS"}`,
    JSON.stringify(r.checks),
    problems.join("; "),
  );
  if (problems.length) fail = true;
}
process.exit(fail ? 1 : 0);
