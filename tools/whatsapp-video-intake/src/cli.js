import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

import wppconnect from '@wppconnect-team/wppconnect';

import {
  ALLOWED_GROUP_NAME,
  DEFAULT_MAX_PAGES,
  GROUP_INTAKE_ROOT,
  NO_PROGRESS_LIMIT,
  SESSION_NAME,
  SESSION_ROOT,
} from './config.js';
import { collectHistory, createReadOnlyClient } from './collector.js';

function parseMaxPages(argv) {
  const index = argv.indexOf('--max-pages');
  if (index === -1) return DEFAULT_MAX_PAGES;
  const value = Number(argv[index + 1]);
  if (!Number.isInteger(value) || value < 1 || value > 5000) {
    throw new Error('--max-pages must be an integer between 1 and 5000');
  }
  return value;
}

async function writePrivateJson(file, value) {
  await fs.writeFile(file, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
}

async function saveQr(base64Qr, attempt) {
  const qrFile = path.join(SESSION_ROOT, 'qr.png');
  const payload = String(base64Qr).replace(/^data:image\/png;base64,/, '');
  await fs.writeFile(qrFile, Buffer.from(payload, 'base64'), { mode: 0o600 });
  await writePrivateJson(path.join(SESSION_ROOT, 'status.json'), {
    status: 'awaiting_qr_scan',
    attempt,
    qr_file: qrFile,
    generated_at: new Date().toISOString(),
    allowed_group: ALLOWED_GROUP_NAME,
  });
  console.log(`QR ready at ${qrFile} (attempt ${attempt})`);
}

async function installBrowserWriteGuards(client) {
  await client.page.evaluate(() => {
    window.__WS_READ_ONLY_BLOCKS = [];
    const patch = (target, namespace) => {
      if (!target) return;
      for (const key of Object.keys(target)) {
        const forbidden = /^(send|reply|react|forward|delete|revoke|clear|archive|pin|mute|mark|set)/i.test(key);
        if (!forbidden || typeof target[key] !== 'function') continue;
        try {
          Object.defineProperty(target, key, {
            configurable: true,
            value: (...args) => {
              window.__WS_READ_ONLY_BLOCKS.push({
                method: `${namespace}.${key}`,
                at: new Date().toISOString(),
                argument_count: args.length,
              });
              throw new Error(`Blocked by WS read-only intake guard: ${namespace}.${key}`);
            },
          });
        } catch {
          window.__WS_READ_ONLY_BLOCKS.push({
            method: `${namespace}.${key}`,
            at: new Date().toISOString(),
            guard_install_failed: true,
          });
        }
      }
    };
    patch(window.WPP?.chat, 'WPP.chat');
    patch(window.WPP?.conn, 'WPP.conn');
    patch(window.WPP?.group, 'WPP.group');
    patch(window.WPP?.status, 'WPP.status');
  });
}

async function main() {
  const maxPages = parseMaxPages(process.argv.slice(2));
  await fs.mkdir(SESSION_ROOT, { recursive: true, mode: 0o700 });
  await fs.mkdir(GROUP_INTAKE_ROOT, { recursive: true, mode: 0o700 });
  await fs.chmod(SESSION_ROOT, 0o700);
  await fs.chmod(GROUP_INTAKE_ROOT, 0o700);

  await writePrivateJson(path.join(SESSION_ROOT, 'status.json'), {
    status: 'starting',
    allowed_group: ALLOWED_GROUP_NAME,
    started_at: new Date().toISOString(),
  });

  let rawClient;
  try {
    rawClient = await wppconnect.create({
      session: SESSION_NAME,
      headless: 'shell',
      useChrome: false,
      waitForLogin: true,
      logQR: false,
      disableWelcome: true,
      updatesLog: false,
      autoClose: 0,
      deviceSyncTimeout: 300000,
      deviceName: 'WS Marketing Intake (read-only)',
      folderNameToken: path.join(SESSION_ROOT, 'tokens'),
      puppeteerOptions: {
        userDataDir: path.join(SESSION_ROOT, 'browser-profile'),
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      },
      catchQR: (base64Qr, _asciiQr, attempt) => {
        void saveQr(base64Qr, attempt).catch((error) => {
          console.error(`Could not save QR: ${error.message}`);
        });
      },
      statusFind: (status) => {
        console.log(`WPPConnect status: ${status}`);
      },
    });

    await fs.rm(path.join(SESSION_ROOT, 'qr.png'), { force: true });
    await rawClient.setOnlinePresence(false);
    await installBrowserWriteGuards(rawClient);
    const client = createReadOnlyClient(rawClient);

    await writePrivateJson(path.join(SESSION_ROOT, 'status.json'), {
      status: 'collecting',
      allowed_group: ALLOWED_GROUP_NAME,
      started_at: new Date().toISOString(),
    });

    const result = await collectHistory({
      client,
      allowedGroupName: ALLOWED_GROUP_NAME,
      intakeRoot: GROUP_INTAKE_ROOT,
      maxPages,
      noProgressLimit: NO_PROGRESS_LIMIT,
      onProgress: ({ pagesAttempted, loadedMessages, added }) => {
        console.log(
          `History page ${pagesAttempted}: ${loadedMessages} messages observed (${added} newly exposed)`,
        );
      },
    });

    const guardEvents = await rawClient.page.evaluate(
      () => window.__WS_READ_ONLY_BLOCKS || [],
    );
    await writePrivateJson(path.join(SESSION_ROOT, 'status.json'), {
      status: 'complete',
      allowed_group: ALLOWED_GROUP_NAME,
      completed_at: new Date().toISOString(),
      report_file: result.reportFile,
      manifest_file: result.manifestFile,
      browser_write_guard_events: guardEvents,
    });
    console.log(JSON.stringify(result.report, null, 2));
  } catch (error) {
    await writePrivateJson(path.join(SESSION_ROOT, 'status.json'), {
      status: 'failed',
      allowed_group: ALLOWED_GROUP_NAME,
      failed_at: new Date().toISOString(),
      error: String(error?.message || error),
    });
    throw error;
  } finally {
    if (rawClient) await rawClient.close().catch(() => {});
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
