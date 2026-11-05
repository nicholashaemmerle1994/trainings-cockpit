import puppeteer from "puppeteer-core";

// Am Mac liegt Chrome im App-Bundle, auf dem Homeserver ist Chromium
// installiert. CHROME_PATH überschreibt beides.
const CHROME =
  process.env.CHROME_PATH ??
  (process.platform === "darwin"
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : "/usr/bin/chromium");

const url = process.argv[2] ?? "http://127.0.0.1:8010/";
const outDir = process.env.SHOT_OUT ?? "../data/screens";
const prefix = process.env.SHOT_PREFIX ?? "audit";
const scale = Number(process.env.SHOT_SCALE ?? "");
const viewportOnly = process.env.SHOT_VIEWPORT === "1";
const waitFor = process.env.SHOT_WAIT ?? ".dial-score";
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
});

const PAGES = (process.env.SHOT_PAGES ?? "Heute,Verpflegung,Aktivitäten")
  .split(",")
  .map((label) => label.trim())
  .filter(Boolean);

async function shoot(width, height, suffix, mobile) {
  const page = await browser.newPage();
  await page.setViewport({
    width,
    height,
    deviceScaleFactor: Number.isFinite(scale) && scale > 0 ? scale : mobile ? 2 : 1,
    isMobile: mobile,
    hasTouch: mobile,
  });
  await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector(waitFor, { timeout: 15000 }).catch(() => undefined);
  await new Promise((resolve) => setTimeout(resolve, 500));
  for (const label of PAGES) {
    await page.evaluate((text) => {
      const button = [...document.querySelectorAll(".tabbar button, .nav button")].find((node) =>
        node.textContent?.includes(text),
      );
      button?.click();
    }, label);
    await new Promise((resolve) => setTimeout(resolve, 1400));
    const slug = label === "Aktivitäten" ? "aktivitaeten" : label.toLowerCase();
    await page.screenshot({
      path: `${outDir}/${prefix}-${slug}-${suffix}.png`,
      fullPage: !viewportOnly,
    });
  }
  console.log("ok", suffix);
  await page.close();
}

try {
  await shoot(1440, 900, "desktop", false);
  await shoot(390, 844, "mobile", true);
} finally {
  await browser.close();
}
