import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';

const VIDEO_TYPES = new Set(['video', 'ptv']);
const READ_ONLY_METHODS = new Set([
  'close',
  'downloadMedia',
  'getAllMessagesInChat',
  'getContact',
  'getMessages',
  'listChats',
  'loadEarlierMessages',
]);

function serialisedId(value) {
  if (typeof value === 'string') return value;
  return value?._serialized || value?.id || String(value || '');
}

function timestampOf(message) {
  const raw = Number(message.timestamp ?? message.t);
  return Number.isFinite(raw) && raw > 0 ? raw : null;
}

function isoDate(epochSeconds) {
  return epochSeconds === null
    ? null
    : new Date(epochSeconds * 1000).toISOString();
}

function messageId(message) {
  return serialisedId(message.id);
}

function senderName(message) {
  return (
    message.notifyName ||
    message.sender?.pushname ||
    message.sender?.name ||
    serialisedId(message.author) ||
    'Unknown sender'
  );
}

function captionOf(message) {
  return String(message.caption ?? message.body ?? '').trim();
}

function mimeExtension(mime) {
  const clean = String(mime || '').split(';', 1)[0].toLowerCase();
  const known = {
    'video/mp4': '.mp4',
    'video/quicktime': '.mov',
    'video/webm': '.webm',
    'video/3gpp': '.3gp',
    'video/x-matroska': '.mkv',
  };
  return known[clean] || '.mp4';
}

function decodeMedia(payload) {
  if (typeof payload !== 'string' || payload.length === 0) {
    throw new Error('WPPConnect returned no media payload');
  }

  const match = payload.match(/^data:([^;,]+)?(?:;charset=[^;,]+)?;base64,(.+)$/s);
  const mime = match?.[1] || null;
  const raw = match?.[2] || payload;
  const buffer = Buffer.from(raw, 'base64');
  if (buffer.length === 0) throw new Error('Decoded media is empty');
  return { buffer, mime };
}

async function writeJsonAtomic(file, value) {
  const temporary = `${file}.tmp-${process.pid}`;
  await fs.writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, {
    mode: 0o600,
  });
  await fs.rename(temporary, file);
}

async function loadManifest(file, groupName) {
  try {
    const parsed = JSON.parse(await fs.readFile(file, 'utf8'));
    if (parsed.group !== groupName || !Array.isArray(parsed.items)) {
      throw new Error('Existing manifest does not match the allowlisted group');
    }
    return parsed;
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    return {
      schema_version: 1,
      group: groupName,
      items: [],
    };
  }
}

function dateRange(messages) {
  const timestamps = messages.map(timestampOf).filter((value) => value !== null);
  if (timestamps.length === 0) return { oldest: null, newest: null };
  return {
    oldest: isoDate(Math.min(...timestamps)),
    newest: isoDate(Math.max(...timestamps)),
  };
}

export function createReadOnlyClient(client) {
  return new Proxy(client, {
    get(target, property, receiver) {
      const value = Reflect.get(target, property, receiver);
      if (typeof value !== 'function') return value;
      if (!READ_ONLY_METHODS.has(String(property))) {
        throw new Error(`Blocked non-read-only WhatsApp method: ${String(property)}`);
      }
      return value.bind(target);
    },
  });
}

export function resolveAllowedGroup(chats, allowedGroupName) {
  const exact = chats.filter(
    (chat) => chat.isGroup === true && chat.name === allowedGroupName,
  );
  if (exact.length !== 1) {
    throw new Error(
      `Expected exactly one allowlisted group named "${allowedGroupName}"; found ${exact.length}`,
    );
  }
  const groupId = serialisedId(exact[0].id);
  if (!groupId.endsWith('@g.us')) {
    throw new Error('The exact allowlist match does not have a WhatsApp group ID');
  }
  return { chat: exact[0], groupId };
}

export async function collectHistory({
  client,
  allowedGroupName,
  intakeRoot,
  maxPages,
  noProgressLimit,
  now = () => new Date(),
  onProgress = () => {},
}) {
  await fs.mkdir(path.join(intakeRoot, 'videos'), { recursive: true, mode: 0o700 });
  await fs.mkdir(path.join(intakeRoot, 'reports'), { recursive: true, mode: 0o700 });
  await fs.mkdir(path.join(intakeRoot, 'manual-export'), {
    recursive: true,
    mode: 0o700,
  });

  const chats = await client.listChats({ onlyGroups: true });
  const { chat, groupId } = resolveAllowedGroup(chats, allowedGroupName);
  const unreadBefore = Number.isFinite(Number(chat.unreadCount))
    ? Number(chat.unreadCount)
    : null;

  let messages = await client.getAllMessagesInChat(groupId, true, false);
  let knownIds = new Set(messages.map(messageId).filter(Boolean));
  let pagesAttempted = 0;
  let consecutiveNoProgress = 0;
  let stopReason = 'page_limit';
  let historyError = null;

  while (pagesAttempted < maxPages) {
    pagesAttempted += 1;
    try {
      await client.loadEarlierMessages(groupId);
    } catch (error) {
      stopReason = 'history_load_error';
      historyError = String(error?.message || error);
      break;
    }

    const next = await client.getAllMessagesInChat(groupId, true, false);
    const nextIds = new Set(next.map(messageId).filter(Boolean));
    let added = 0;
    for (const id of nextIds) if (!knownIds.has(id)) added += 1;
    messages = next;
    knownIds = nextIds;
    consecutiveNoProgress = added === 0 ? consecutiveNoProgress + 1 : 0;
    onProgress({ pagesAttempted, loadedMessages: messages.length, added });

    if (consecutiveNoProgress >= noProgressLimit) {
      stopReason = 'no_further_history_observed';
      break;
    }
  }

  const freshChats = await client.listChats({ onlyGroups: true });
  const { chat: freshChat, groupId: freshGroupId } = resolveAllowedGroup(
    freshChats,
    allowedGroupName,
  );
  if (freshGroupId !== groupId) throw new Error('Allowlisted group ID changed during run');
  const unreadAfter = Number.isFinite(Number(freshChat.unreadCount))
    ? Number(freshChat.unreadCount)
    : null;

  const manifestFile = path.join(intakeRoot, 'manifest.json');
  const manifest = await loadManifest(manifestFile, allowedGroupName);
  await writeJsonAtomic(manifestFile, manifest);
  const existingMessageIds = new Set(manifest.items.map((item) => item.message_id));
  const checksumOwners = new Map();
  for (const item of manifest.items) {
    if (item.sha256 && item.file && !item.duplicate_of) {
      checksumOwners.set(item.sha256, item.file);
    }
  }

  const videos = messages
    .filter((message) => VIDEO_TYPES.has(String(message.type).toLowerCase()))
    .sort((left, right) => (timestampOf(left) || 0) - (timestampOf(right) || 0));
  const counters = {
    video_messages_observed: videos.length,
    downloaded: 0,
    duplicates: 0,
    already_recorded: 0,
    unavailable: 0,
  };
  const unavailable = [];

  for (const message of videos) {
    const id = messageId(message);
    if (!id) {
      counters.unavailable += 1;
      unavailable.push({ message_id: null, reason: 'Message has no stable ID' });
      continue;
    }
    if (existingMessageIds.has(id)) {
      counters.already_recorded += 1;
      continue;
    }

    try {
      const downloaded = decodeMedia(await client.downloadMedia(id));
      const checksum = crypto.createHash('sha256').update(downloaded.buffer).digest('hex');
      const effectiveMime = downloaded.mime || message.mimetype || 'video/mp4';
      const owner = checksumOwners.get(checksum);
      const epoch = timestampOf(message);
      const stamp = (isoDate(epoch) || 'unknown-date').replaceAll(/[-:.]/g, '');
      const idHash = crypto.createHash('sha256').update(id).digest('hex').slice(0, 16);
      let relativeFile = owner || null;
      let duplicateOf = null;

      if (owner) {
        counters.duplicates += 1;
        duplicateOf = owner;
      } else {
        relativeFile = path.join(
          'videos',
          `${stamp}_${idHash}${mimeExtension(effectiveMime)}`,
        );
        await fs.writeFile(path.join(intakeRoot, relativeFile), downloaded.buffer, {
          mode: 0o600,
          flag: 'wx',
        });
        checksumOwners.set(checksum, relativeFile);
        counters.downloaded += 1;
      }

      manifest.items.push({
        group: allowedGroupName,
        date: isoDate(epoch),
        sender: senderName(message),
        caption: captionOf(message),
        message_id: id,
        sha256: checksum,
        file: relativeFile,
        duplicate_of: duplicateOf,
      });
      existingMessageIds.add(id);
      await writeJsonAtomic(manifestFile, manifest);
    } catch (error) {
      counters.unavailable += 1;
      unavailable.push({ message_id: id, reason: String(error?.message || error) });
    }
  }

  const runAt = now();
  const runId = runAt.toISOString().replaceAll(/[-:.]/g, '');
  const report = {
    schema_version: 1,
    run_at: runAt.toISOString(),
    mode: 'local_read_only_allowlisted_history_probe',
    group: allowedGroupName,
    history: {
      pages_attempted: pagesAttempted,
      stop_reason: stopReason,
      error: historyError,
      messages_observed: messages.length,
      observed_range: dateRange(messages),
      video_range: dateRange(videos),
      end_of_history_proven: false,
      interpretation:
        stopReason === 'no_further_history_observed'
          ? 'No older messages appeared after repeated requests. This is the observed synchronisation boundary, not proof of the group creation date.'
          : 'The observed boundary is incomplete; review the stop reason before drawing conclusions.',
    },
    unread_count: {
      before: unreadBefore,
      after: unreadAfter,
      unchanged: unreadBefore === null || unreadAfter === null
        ? null
        : unreadBefore === unreadAfter,
      caveat: 'A concurrent read on another linked device can also change this count.',
    },
    media: counters,
    unavailable,
  };

  const reportFile = path.join(intakeRoot, 'reports', `run-${runId}.json`);
  await writeJsonAtomic(reportFile, report);
  return { report, reportFile, manifestFile };
}
