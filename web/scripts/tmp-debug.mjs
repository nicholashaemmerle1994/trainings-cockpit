import puppeteer from "puppeteer-core";

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
});

try {
  const page = await browser.newPage();
  page.on("console", (msg) => console.log("console:", msg.text()));
  page.on("pageerror", (err) => console.log("pageerror:", err.message));
  page.on("request", (req) => {
    if (req.url().includes("vendor")) console.log("request:", req.method(), req.url());
  });
  page.on("response", (res) => {
    if (res.url().includes("vendor")) console.log("response:", res.status());
  });
  await page.setViewport({ width: 390, height: 1000, deviceScaleFactor: 1 });
  await page.goto("http://127.0.0.1:8011/", { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector(".vendor-row input", { timeout: 15000 });
  console.log("vorher:", await page.$eval(".vendor-row input", (n) => n.value));
  await page.focus(".vendor-row input");
  await page.$eval(".vendor-row input", (n) => {
    n.value = "";
  });
  await page.type(".vendor-row input", "77");
  console.log("getippt:", await page.$eval(".vendor-row input", (n) => n.value));
  await page.keyboard.press("Enter");
  await new Promise((resolve) => setTimeout(resolve, 1200));
  console.log("karte:", JSON.stringify(await page.$eval(".vendor", (n) => n.innerText)));
} finally {
  await browser.close();
}
