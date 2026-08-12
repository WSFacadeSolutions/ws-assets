import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import {
  collectHistory,
  createReadOnlyClient,
  resolveAllowedGroup,
} from '../src/collector.js';

const GROUP = 'WS614_11 Weonga rd, Dover Heights';
const GROUP_ID = '120000000000000000@g.us';

function chat(name = GROUP, unreadCount = 4) {
  return {
    id: { _serialized: GROUP_ID },
    isGroup: true,
    name,
    unreadCount,
  };
}

function message(id, type, timestamp, body = '') {
  return {
    id,
    type,
    timestamp,
    body,
    notifyName: 'Site sender',
    mimetype: type === 'video' ? 'video/mp4' : 'image/jpeg',
  };
}

test('the allowlist requires one exact group-title match', () => {
  assert.equal(resolveAllowedGroup([chat()], GROUP).groupId, GROUP_ID);
  assert.throws(
    () => resolveAllowedGroup([chat(`${GROUP} copy`)], GROUP),
    /found 0/,
  );
  assert.throws(
    () => resolveAllowedGroup([chat(), chat()], GROUP),
    /found 2/,
  );
});

test('the client facade blocks every method not explicitly read-only', async () => {
  const calls = [];
  const raw = {
    listChats() {
      calls.push('listChats');
      return [];
    },
    sendText() {
      calls.push('sendText');
    },
  };
  const client = createReadOnlyClient(raw);
  await client.listChats();
  assert.deepEqual(calls, ['listChats']);
  assert.throws(() => client.sendText(), /Blocked non-read-only/);
  assert.deepEqual(calls, ['listChats']);
});

test('history probing downloads videos only and deduplicates by checksum', async () => {
  const intakeRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ws-wa-intake-'));
  const first = message('m1', 'chat', 1000, 'text');
  const videoA = message('m2', 'video', 900, 'First caption');
  const image = message('m3', 'image', 800);
  const videoDuplicate = message('m4', 'video', 700, 'Second caption');
  const pages = [
    [first, videoA],
    [first, videoA, image, videoDuplicate],
    [first, videoA, image, videoDuplicate],
    [first, videoA, image, videoDuplicate],
  ];
  let page = 0;
  const payload = `data:video/mp4;base64,${Buffer.from('same-video').toString('base64')}`;
  const client = {
    async listChats() {
      return [chat()];
    },
    async getAllMessagesInChat() {
      return pages[page];
    },
    async loadEarlierMessages() {
      page = Math.min(page + 1, pages.length - 1);
    },
    async downloadMedia() {
      return payload;
    },
  };

  const { report, manifestFile } = await collectHistory({
    client,
    allowedGroupName: GROUP,
    intakeRoot,
    maxPages: 10,
    noProgressLimit: 2,
    now: () => new Date('2026-08-12T06:00:00.000Z'),
  });
  const manifest = JSON.parse(await fs.readFile(manifestFile, 'utf8'));
  const videoFiles = await fs.readdir(path.join(intakeRoot, 'videos'));

  assert.equal(report.history.stop_reason, 'no_further_history_observed');
  assert.equal(report.history.end_of_history_proven, false);
  assert.equal(report.media.video_messages_observed, 2);
  assert.equal(report.media.downloaded, 1);
  assert.equal(report.media.duplicates, 1);
  assert.equal(report.unread_count.unchanged, true);
  assert.equal(manifest.items.length, 2);
  assert.equal(manifest.items[0].caption, 'Second caption');
  assert.equal(manifest.items[1].caption, 'First caption');
  assert.equal(manifest.items[0].sha256, manifest.items[1].sha256);
  assert.equal(videoFiles.length, 1);
});

test('media failures are reported without creating manifest records', async () => {
  const intakeRoot = await fs.mkdtemp(path.join(os.tmpdir(), 'ws-wa-intake-'));
  const client = {
    async listChats() {
      return [chat(GROUP, 0)];
    },
    async getAllMessagesInChat() {
      return [message('unavailable', 'video', 600)];
    },
    async loadEarlierMessages() {},
    async downloadMedia() {
      throw new Error('media no longer available');
    },
  };

  const { report, manifestFile } = await collectHistory({
    client,
    allowedGroupName: GROUP,
    intakeRoot,
    maxPages: 1,
    noProgressLimit: 3,
  });
  const manifest = JSON.parse(await fs.readFile(manifestFile, 'utf8'));
  assert.equal(report.history.stop_reason, 'page_limit');
  assert.equal(report.media.unavailable, 1);
  assert.match(report.unavailable[0].reason, /no longer available/);
  assert.deepEqual(manifest.items, []);
});
