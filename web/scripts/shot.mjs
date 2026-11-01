import puppeteer from "puppeteer-core";

const name = process.argv[2] ?? "today";
const width = Number(process.argv[3] ?? 1440);
const height = Number(process.argv[4] ?? 1300);
const url = process.argv[5] ?? "http://127.0.0.1:8000/";
const tab = process.argv[6];

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector(".dial-score", { timeout: 15000 });
  if (tab) {
    await page.evaluate((label) => {
      const button = [...document.querySelectorAll(".nav button")].find((node) =>
        node.textContent?.includes(label),
      );
      button?.click();
    }, tab);
  }
  await page
    .waitForFunction(
      () => {
        const chart = document.querySelector(".chart-svg");
        return !chart || chart.getBoundingClientRect().width > 300;
      },
      { timeout: 10000 },
    )
    .catch(() => undefined);
  await new Promise((resolve) => setTimeout(resolve, 1000));
  await page.screenshot({ path: `../data/screens/${name}.png`, fullPage: false });
  console.log(`saved ../data/screens/${name}.png`);
} finally {
  await browser.close();
}
