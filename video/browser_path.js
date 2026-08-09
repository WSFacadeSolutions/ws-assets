const fs = require('fs');

function browserPath() {
  const candidates = [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
    '/root/.cache/puppeteer/chrome-headless-shell/linux-148.0.7778.97/chrome-headless-shell-linux64/chrome-headless-shell',
  ].filter(Boolean);
  const found = candidates.find(p => fs.existsSync(p));
  if (!found) {
    throw new Error('Chrome/Chromium not found. Install Google Chrome or set CHROME_PATH.');
  }
  return found;
}

module.exports = { browserPath };
