import puppeteer from "puppeteer-core";

const [url, out, width = "1440", height = "1200", mobile = ""] = process.argv.slice(2);

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
});

try {
  const page = await browser.newPage();
  const isMobile = mobile === "mobile";
  await page.setViewport({
    width: Number(width),
    height: Number(height),
    deviceScaleFactor: isMobile ? 2 : 1,
    isMobile,
    hasTouch: isMobile,
  });
  await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 });
  await page.evaluate(() => document.fonts.ready);
  await new Promise((resolve) => setTimeout(resolve, 600));
  await page.screenshot({ path: out, fullPage: true });
  console.log(out);
} finally {
  await browser.close();
}
