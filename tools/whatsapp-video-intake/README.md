# WS WhatsApp video intake proof of concept

This is a local, allowlisted and read-only history probe for the single WhatsApp group:

`WS614_11 Weonga rd, Dover Heights`

It is deliberately separate from WST004. It does not read, reuse, migrate or modify
`/root/ws-agents/agents/wst004/auth`, and it does not bind WST004's port or service.
Its browser profile, linked-device session and downloaded media live under:

`/root/ws-marketing-intake/whatsapp/`

Nothing in that runtime directory is an approved marketing asset.

## Safety boundary

- The allowlist is compiled into `src/config.js`; there is no command-line group option.
- The group must have one exact title match and a `@g.us` identifier.
- The collector-facing client exposes only chat listing, history retrieval, media
  download, contact lookup and close operations. Any other WPPConnect method is blocked.
- A second browser-side guard replaces send, reply, reaction, forward, delete, revoke,
  clear, archive, pin, mute, mark and set operations with throwing functions.
- Loaded messages are retrieved with WPPConnect's `getMessages` path. The deprecated
  `getAllMessagesInChat` path is deliberately not exposed because it attempted an internal
  `markIsRead` call during the live proof and was blocked by the browser guard.
- The collector never opens the visual chat UI and never calls `sendSeen`,
  `markUnseenMessage`, `markPlayed` or any sender method.
- The allowlisted chat's unread count is sampled before and after the probe and recorded.
  An unchanged value is useful evidence, but a changed value is not conclusive because
  another linked device may read the chat concurrently.
- QR, browser profile, reports, manifests and media are private to root (`0700` folders,
  `0600` files). The QR is removed immediately after login.

WPPConnect includes sender methods in its full client class. This prototype does not
claim the upstream library is intrinsically read-only; the local facade and browser
guards are the enforcement used by this tool.

## Run and pair safely

```bash
cd /root/ws-assets/tools/whatsapp-video-intake
npm ci
npm test
npm run collect
```

On the first run, the process waits for a new linked device. It writes the current QR to:

`/root/ws-marketing-intake/whatsapp/.wppconnect-marketing-intake/qr.png`

Keep the process running, open that file only through the private workspace, then use
WhatsApp on Guilherme's phone: **Settings → Linked devices → Link a device**. Confirm the
new device name is **WS Marketing Intake (read-only)**. Do not use the WST004 QR page.

The QR is an authentication secret while valid. Never copy it to Git, memory, Plane,
logs, a public web root or a third-party service. If the process is stopped before the QR
is scanned, the code and empty intake remain safe; run the same command again for a fresh
QR.

If QR scanning repeatedly fails, the same isolated session can request WhatsApp's numeric
linked-device code. Supply the account phone number only as the private process environment
variable `WS_WHATSAPP_LINK_PHONE`; the phone number is not written to reports or manifests.
The current short-lived code is saved only in the private session status file and is
replaced by the normal collection status after login.

## What the probe records

The collector pages backwards with WPPConnect's current `getMessages` `before` cursor until
three consecutive requests expose no additional IDs, or until the page limit/error stops
it. The deprecated `loadEarlierMessages` route is not used. It then considers only `video`
and `ptv` messages. Each successful message contributes only:

Immediately after first-device pairing, the WhatsApp chat list can still be empty while
the linked-device synchronisation catches up. The collector waits up to five minutes for
the one exact allowlisted group to appear; it never falls back to a partial-title match.
Before listing chats, it also waits for WhatsApp Web's interface to report `MAIN (NORMAL)`;
the first-device synchronisation is not forced through a short browser timeout.

- group title;
- UTC date;
- sender display name (falling back to the sender identifier only when necessary);
- caption;
- WhatsApp message ID;
- SHA-256 checksum;
- relative intake file and duplicate reference.

The run report states the oldest and newest messages actually observed, the oldest and
newest video observed, the stop reason, media failures and the unread-count sample. Even
when repeated requests show no progress, `end_of_history_proven` remains `false`: that is
the linked device's observed synchronisation boundary, not proof that the group has no
older history.

Checksums deduplicate media across runs and message IDs. A duplicate message receives a
manifest record but not a second video file. An unavailable historical attachment is
reported and is not represented as successfully collected.

## If WhatsApp Web does not expose the required history

Use the phone's native export for this one group: open the group, open group info, choose
**Export chat**, choose **Attach media**, and save/share the archive to a trusted local
machine. Transfer that archive directly to:

`/root/ws-marketing-intake/whatsapp/ws614_11-weonga-rd-dover-heights/manual-export/`

Do not send it through Mailopoly or another cloud inbox. Native exports can have message
and media limits, so preserve the export date and report the oldest message/video actually
contained. The export remains intake: review privacy, client permission and project
provenance before copying any selected file into WS Assets.

## Post-collection gate

After at least one real video is collected, inspect codec/duration, generate contact
sheets and prepare a short Australian-English selection report. Only then nominate a
small Story/Reel cut. Do not build a batch of ten edits before the collection result and
permissions are proven.
