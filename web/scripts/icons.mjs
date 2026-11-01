import puppeteer from "puppeteer-core";

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-gpu"],
});

const markup = `
  <style>
    html, body { margin: 0; width: 100%; height: 100%; background: #0b0d10; }
    body { display: grid; place-items: center; }
    .ring {
      width: 64%; height: 64%; border-radius: 50%;
      background: conic-gradient(from 150deg, #3ddc97, #5b8def 55%, #3ddc97);
      position: relative;
      box-shadow: 0 0 18% rgba(61, 220, 151, 0.35);
    }
    .ring::after {
      content: ""; position: absolute; inset: 15%; border-radius: 50%;
      background: #0b0d10;
    }
  </style>
  <div class="ring"></div>
`;

try {
  for (const [size, name] of [
    [512, "icon-512.png"],
    [192, "icon-192.png"],
    [180, "apple-touch-icon.png"],
  ]) {
    const page = await browser.newPage();
    await page.setViewport({ width: size, height: size, deviceScaleFactor: 1 });
    await page.setContent(markup, { waitUntil: "load" });
    await page.screenshot({ path: `public/icons/${name}` });
    await page.close();
    console.log(`saved public/icons/${name}`);
  }
} finally {
  await browser.close();
}
