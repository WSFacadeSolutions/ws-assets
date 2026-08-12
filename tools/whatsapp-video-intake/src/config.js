import path from 'node:path';

export const ALLOWED_GROUP_NAME = 'WS614_11 Weonga rd, Dover Heights';
export const SESSION_NAME = 'ws-marketing-video-intake';

export const RUNTIME_ROOT = path.resolve(
  process.env.WS_WHATSAPP_INTAKE_ROOT || '/root/ws-marketing-intake/whatsapp',
);

export const SESSION_ROOT = path.join(
  RUNTIME_ROOT,
  '.wppconnect-marketing-intake',
);

export const GROUP_INTAKE_ROOT = path.join(
  RUNTIME_ROOT,
  'ws614_11-weonga-rd-dover-heights',
);

export const DEFAULT_MAX_PAGES = 500;
export const NO_PROGRESS_LIMIT = 3;
