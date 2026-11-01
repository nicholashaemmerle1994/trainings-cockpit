import puppeteer from "puppeteer-core";

const url = process.argv[2] ?? "http://127.0.0.1:8010/";

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"],
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
  await page.goto(url, { waitUntil: "networkidle2", timeout: 30000 });
  await page.waitForSelector(".bevel-field input", { timeout: 15000 });

  const measure = () =>
    page.evaluate(() => {
      const input = document.querySelector(".bevel-field input");
      const box = input.getBoundingClientRect();
      return {
        fontSize: getComputedStyle(input).fontSize,
        inputMode: input.getAttribute("inputmode"),
        enterKeyHint: input.getAttribute("enterkeyhint"),
        width: Math.round(box.width),
        docWidth: document.documentElement.scrollWidth,
        viewport: window.innerWidth,
      };
    });

  console.log("vor Fokus:", await measure());
  await page.focus(".bevel-field input");
  await page.type(".bevel-field input", "9");
  await new Promise((resolve) => setTimeout(resolve, 400));
  console.log("nach Fokus:", await measure());
  await page.screenshot({ path: "../data/screens/mobile-input-fokus.png" });

  // Verpflegung prüfen
  await page.evaluate(() => {
    const button = [...document.querySelectorAll(".tabbar button, .nav button")].find((node) =>
      node.textContent?.includes("Verpflegung"),
    );
    button?.click();
  });
  await page.waitForSelector(".fuel-fields input", { timeout: 15000 });
  await page.waitForSelector(".fuel-hero", { timeout: 15000 }).catch(() => undefined);
  await new Promise((resolve) => setTimeout(resolve, 1200));
  const fuel = await page.evaluate(() =>
    [...document.querySelectorAll(".fuel-fields input, .shot-field input")].map((input) => ({
      value: input.getAttribute("value"),
      fontSize: getComputedStyle(input).fontSize,
      inputMode: input.getAttribute("inputmode"),
    })),
  );
  console.log("Verpflegung:", fuel);
  await page.screenshot({ path: "../data/screens/mobile-fuel.png" });
  console.log("screens gespeichert");
} finally {
  await browser.close();
}
