// Ciphertext relay only: connection/encryption keys and plaintext stay local.
const ABOUT = `Game Time Monitor / Játékfigyelő

Windows játékidő-figyelő, titkosított statisztikai szinkronizálással.

Bejelentkezés és adatkezelés

A GitHub-belépés a kapcsolati kód létrehozására és kezelésére szolgál. A Supabase Auth tárolja a fiókazonosítót, a GitHub-profilt és az ellenőrzött e-mail-címet. Az alkalmazás nem kéri a GitHub-jelszavadat.

A játékidő, a játéknevek és a gép neve titkosítva kerülnek a szerverre. A visszafejtés kulcsa a gépeiden marad. A kapcsolati kód birtokosa hozzáférhet a csoport statisztikáihoz, ezért tartsd titokban.

A szerver a titkosított másolatokat, a csoport és a gépek technikai azonosítóit, valamint a forgalmi keretek számlálóit tárolja. A beállítások, a napi keretek és a programútvonalak helyben maradnak. A szolgáltató saját biztonsági és hozzáférési naplókat is kezelhet.

A 90 napja inaktív gépmásolatokat automatikusan töröljük. A kezelt kód visszavonása vagy cseréje eltávolítja a régi csoport szerveroldali másolatait; a helyi előzmények megmaradnak. A fiók és a visszaélés elleni számlálók törlését az üzemeltetőtől kérheted.

Az ingyenes szolgáltatás korlátozott kapacitású, elérhetősége nem garantált. A helyi követés szinkronizálás nélkül is működik.

English

A Windows game-time monitor with encrypted statistics synchronization. GitHub sign-in manages connection codes. Supabase Auth stores your account ID, GitHub profile and verified email. Statistics are encrypted on your computers; keep your connection code private. Server ciphertext is deleted after 90 inactive days or when the owner revokes/replaces the code. Account and abuse counters require operator-assisted deletion. Local history and settings remain on your computers. The free service has limited capacity and no availability guarantee.

Kapcsolat / Contact: https://github.com/Blintboi
`;
const FORMAT = 'GameTimeMonitor.sync.v1';
const ID = /^[0-9a-f]{32}$/;
const KEY = /^[0-9a-f]{64}$/;
const VERSION = /^[1-9][0-9]{0,18}$/;
const MAX_BODY = 750_000, MAX_BASE64 = 699_052;
const HEADERS = { 'content-type': 'application/json', 'cache-control': 'no-store',
  'x-content-type-options': 'nosniff', 'content-security-policy': "default-src 'none'; frame-ancestors 'none'",
  'referrer-policy': 'no-referrer' };
function reply(status, body, retry = 0) {
  const headers = { ...HEADERS };
  if (retry) headers['retry-after'] = String(Math.max(1, Math.min(86400, Math.floor(retry))));
  return new Response(JSON.stringify(body), { status, headers });
}
function version(value) {
  return typeof value === 'string' && VERSION.test(value) && BigInt(value) < 9223372036854775808n;
}
async function readBody(request, timeoutMs) {
  const reader = request.body?.getReader();
  if (!reader) throw new Error('body');
  let timer;
  const collect = async () => {
    const chunks = []; let size = 0;
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY) throw new Error('body');
      chunks.push(value);
    }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  };
  try {
    return await Promise.race([collect(), new Promise((_, reject) => {
      timer = setTimeout(() => { reject(new Error('timeout')); void reader.cancel().catch(() => {}); }, timeoutMs);
    })]);
  } finally { clearTimeout(timer); void reader.cancel().catch(() => {}); }
}
async function digest(text) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))),
    value => value.toString(16).padStart(2, '0')).join('');
}
function validPayload(value) {
  if (value === null) return true;
  if (typeof value !== 'string' || value.length < 44 || value.length > MAX_BASE64
      || value.length % 4 || !/^[A-Za-z0-9+/]+={0,2}$/.test(value)) return false;
  try {
    const decoded = atob(value);
    return decoded.length >= 32 && decoded.length <= 524288 && decoded.startsWith('GTM1') && btoa(decoded) === value;
  } catch { return false; }
}
export function createHandler({ url, serviceKey, fetcher = fetch, clock = Date.now, bodyTimeoutMs = 5000 }) {
  const admitted = new Map(); let active = 0;
  const rpc = async (name, args) => {
    const response = await fetcher(url.replace(/\/$/, '') + '/rest/v1/rpc/' + name, {
      method: 'POST', headers: { 'content-type': 'application/json', apikey: serviceKey, authorization: 'Bearer ' + serviceKey },
      body: JSON.stringify(args), signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) throw new Error('storage');
    return response.json();
  };
  const authorized = async group => {
    const cached = admitted.get(group);
    if (cached && cached.until > clock()) return cached.allowed;
    const allowed = await rpc('gametime_sync_authorize', { p_group: group }) === true;
    if (admitted.size >= 512) admitted.delete(admitted.keys().next().value);
    admitted.set(group, { allowed, until: clock() + 15000 });
    return allowed;
  };
  const handle = async function(request) {
    if (request.method === 'GET' && new URL(request.url).pathname.endsWith('/about')) return new Response(ABOUT,
      {status:200,headers:{...HEADERS,'content-type':'text/plain; charset=utf-8'}});
    if (request.method === 'GET' && new URL(request.url).pathname.endsWith('/health')) return reply(200, { format: FORMAT, status: 'ok' });
    if (request.method !== 'POST') return reply(405, { error: 'method' });
    const authorization = request.headers.get('authorization') || '';
    if (!authorization.startsWith('Bearer ') || !KEY.test(authorization.slice(7))) return reply(401, { error: 'credential' });
    if (!/^application\/json(?:\s*;|$)/i.test(request.headers.get('content-type') || '')
        || !['', 'identity'].includes(request.headers.get('content-encoding') || '')) return reply(415, { error: 'content_type' });
    const length = request.headers.get('content-length');
    if (length && (!/^[0-9]{1,9}$/.test(length) || Number(length) > MAX_BODY)) return reply(413, { error: 'body' });
    if (!url || !serviceKey) return reply(503, { error: 'configuration' }, 300);
    if (active >= 8) return reply(503, { error: 'busy' }, 60);
    active++;
    try {
      const group = await digest(authorization.slice(7));
      // Unknown keys allocate no rows and do not cause large bodies to be parsed.
      if (!await authorized(group)) return reply(403, { error: 'admission' }, 3600);
      let body;
      try {
        body = await readBody(request, bodyTimeoutMs);
        if (!body || body.format !== FORMAT || typeof body.device !== 'string' || !ID.test(body.device) || !version(body.revision)
            || Object.keys(body).some(key => !['format', 'device', 'revision', 'known', 'payload'].includes(key))
            || !body.known || Array.isArray(body.known) || typeof body.known !== 'object'
            || Object.keys(body.known).length > 100 || !validPayload(body.payload)) throw new Error('body');
        for (const [device, revision] of Object.entries(body.known)) if (!ID.test(device) || !version(revision)) throw new Error('body');
      } catch { return reply(400, { error: 'body' }); }
      // The last proxy-added address is used only as an additional throttle.
      // Admission, device/group limits and hard global budgets remain decisive.
      const ip = (request.headers.get('x-forwarded-for') || 'unknown').split(',').at(-1).trim().slice(0, 80);
      const ipKey = await crypto.subtle.importKey('raw', new TextEncoder().encode(serviceKey),
        { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
      const ipHash = Array.from(new Uint8Array(await crypto.subtle.sign('HMAC', ipKey, new TextEncoder().encode(ip))),
        value => value.toString(16).padStart(2, '0')).join('');
      const result = await rpc('gametime_sync_exchange', { p_group: group, p_ip: ipHash,
        p_device: body.device, p_revision: body.revision, p_payload: body.payload, p_known: body.known });
      if (result.error === 'rate') return reply(429, { error: 'rate' }, result.retry_after || 60);
      if (result.error === 'quota') return reply(507, { error: 'quota' }, result.retry_after || 3600);
      if (result.error === 'admission') { admitted.delete(group); return reply(403, { error: 'admission' }, 3600); }
      if (result.error) return reply(503, { error: 'unavailable' }, 300);
      if (typeof result.need_upload !== 'boolean' || !Array.isArray(result.snapshots) || result.snapshots.length > 20) throw new Error('storage');
      return reply(200, { format: FORMAT, need_upload: result.need_upload, snapshots: result.snapshots });
    } catch { return reply(503, { error: 'unavailable' }, 300); }
    finally { active--; }
  };
  return async function(request) {
    try { return await handle(request); }
    finally {
      // Do not leave an unread upload attached to a rejected request.
      if (request.body && !request.body.locked) void request.body.cancel().catch(() => {});
    }
  };
}
