// Statistics stay encrypted. This function never receives the connection code
// or encryption key. Database administration credentials remain server-side.
const FORMAT = 'GameTimeMonitor.sync.v1';
const ID = /^[0-9a-f]{32}$/;
const KEY = /^[0-9a-f]{64}$/;
const VERSION = /^[1-9][0-9]{0,18}$/;
const MAX_BODY = 750_000;
const MAX_BASE64 = 699_052; // 512 KiB, base64 encoded
const HEADERS = { 'content-type': 'application/json', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff' };

function reply(status, body) {
  return new Response(JSON.stringify(body), { status, headers: HEADERS });
}

function version(value) {
  return typeof value === 'string' && VERSION.test(value) && BigInt(value) < 9223372036854775808n;
}

async function readBody(request) {
  const reader = request.body?.getReader();
  if (!reader) throw new Error('body');
  const chunks = []; let size = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY) throw new Error('body');
      chunks.push(value);
    }
  } finally { await reader.cancel(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}

async function sha256(text) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))),
    value => value.toString(16).padStart(2, '0')).join('');
}

export function createHandler({ url, serviceKey, fetcher = fetch }) {
  return async function handle(request) {
    if (request.method === 'GET' && new URL(request.url).pathname.endsWith('/health')) {
      return reply(200, { format: FORMAT, status: 'ok' });
    }
    if (request.method !== 'POST') return reply(405, { error: 'method' });
    const authorization = request.headers.get('authorization') || '';
    if (!authorization.startsWith('Bearer ') || !KEY.test(authorization.slice(7))) {
      return reply(401, { error: 'credential' });
    }
    if (!(request.headers.get('content-type') || '').startsWith('application/json')) {
      return reply(415, { error: 'content_type' });
    }
    let body;
    try {
      body = await readBody(request);
      if (!body || body.format !== FORMAT || !ID.test(body.device) || !version(body.revision)
          || !body.known || Array.isArray(body.known) || typeof body.known !== 'object'
          || Object.keys(body.known).length > 100) throw new Error('body');
      for (const [device, revision] of Object.entries(body.known)) {
        if (!ID.test(device) || !version(revision)) throw new Error('body');
      }
      if (body.payload !== null && (typeof body.payload !== 'string'
          || body.payload.length < 44 || body.payload.length > MAX_BASE64
          || body.payload.length % 4 !== 0 || !/^[A-Za-z0-9+/]+={0,2}$/.test(body.payload))) throw new Error('body');
    } catch { return reply(400, { error: 'body' }); }
    if (!url || !serviceKey) return reply(503, { error: 'configuration' });
    try {
      const group = await sha256(authorization.slice(7));
      // Hash IPs with the server secret; neither raw IP nor bearer token is stored.
      const ip = (request.headers.get('x-forwarded-for') || 'unknown').split(',')[0].trim().slice(0, 80);
      const ipKey = await crypto.subtle.importKey('raw', new TextEncoder().encode(serviceKey),
        { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      const ipHash = Array.from(new Uint8Array(await crypto.subtle.sign('HMAC', ipKey, new TextEncoder().encode(ip))),
        value => value.toString(16).padStart(2, '0')).join('');
      const response = await fetcher(url.replace(/\/$/, '') + '/rest/v1/rpc/gametime_sync_exchange', {
        method: 'POST', headers: { 'content-type': 'application/json', apikey: serviceKey, authorization: 'Bearer ' + serviceKey },
        body: JSON.stringify({ p_group: group, p_ip: ipHash, p_device: body.device, p_revision: body.revision,
          p_payload: body.payload, p_known: body.known }),
        signal: AbortSignal.timeout(10_000),
      });
      if (!response.ok) return reply(503, { error: 'storage' });
      const result = await response.json();
      if (result.error === 'rate') return reply(429, { error: 'rate' });
      if (result.error === 'quota') return reply(507, { error: 'quota' });
      if (result.error) return reply(503, { error: 'storage' });
      return reply(200, { format: FORMAT, ...result });
    } catch { return reply(503, { error: 'unavailable' }); }
  };
}
