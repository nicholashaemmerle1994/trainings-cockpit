import puppeteer from "puppeteer-core";

// Am Mac liegt Chrome im App-Bundle, auf dem Homeserver ist Chromium
// installiert. CHROME_PATH überschreibt beides.
const CHROME =
  process.env.CHROME_PATH ??
  (process.platform === "darwin"
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : "/usr/bin/chromium");

const url = process.argv[2] ?? "http://127.0.0.1:8010/";
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
});

const PAGES = ["Heute", "Verpflegung", "Aktivitäten"];

async function shoot(width, height, suffix, mobile) {
  const page = await browser.newPage();
  await page.setViewport({
    width,
    height,
    deviceScaleFactor: mobile ? 2 : 1,
    isMobile: mobile,
    hasTouch: mobile,
  });
  await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector(".dial-score", { timeout: 15000 }).catch(() => undefined);
  for (const label of PAGES) {
    await page.evaluate((text) => {
      const button = [...document.querySelectorAll(".tabbar button, .nav button")].find((node) =>
        node.textContent?.includes(text),
      );
      button?.click();
    }, label);
    await new Promise((resolve) => setTimeout(resolve, 1400));
    const slug = label === "Aktivitäten" ? "aktivitaeten" : label.toLowerCase();
    await page.screenshot({ path: `../data/screens/audit-${slug}-${suffix}.png`, fullPage: true });
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
