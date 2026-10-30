import { randomUUID } from 'node:crypto'
import { spawnSync } from 'node:child_process'
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const GCAPTCHA_BASE = 'https://gcaptcha4.geetest.com'
const STATIC_BASE = 'https://static.geetest.com'
const CONFIG_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'wulu_geetest_bypass', 'data')

// Probing several sites: one can be pinned to a stale (or ahead-of-fleet) build. The demo
// site is excluded -- it lags by design, so it would keep succeeding while production
// failed and mask a honeypot trip. Deduped: a repeated id would fake the cross-check below.
const CAPTCHA_IDS = [...new Set([
  '4a20b69644e17d023b92a381c30968b1',
  'e392e1d7fd421dc63325744d5a2b9c73',
])]

const argv = process.argv.slice(2)
// A local SDK file is offline debug only, and read-only: the version key still
// comes from the live API, so writing would file it under the wrong build.
const localFile = argv.find((a) => !a.startsWith('--')) || null
const dryRun = argv.includes('--dry-run') || Boolean(localFile)

if (localFile && !existsSync(localFile)) throw new Error(`local SDK file not found: ${localFile}`)

const isObject = (v) => typeof v === 'object' && v !== null && !Array.isArray(v)

function warn(msg) {
  console.warn(`[warn] ${msg}`)
  if (process.env.GITHUB_ACTIONS) console.log(`::warning::${msg}`)
}

function configPath(staticVer) {
  return path.join(CONFIG_DIR, `${staticVer.match(/^(v?\d+\.\d+\.\d+)/)?.[0] ?? staticVer}-config.json`)
}

function loadConfig(staticVer) {
  const file = configPath(staticVer)
  if (!existsSync(file)) return {}

  let parsed
  try {
    parsed = JSON.parse(readFileSync(file, 'utf8'))
  } catch (e) {
    throw new Error(`corrupt config ${file}: ${e.message}`)
  }
  // Spreading null/array/scalar would silently drop every other build in the file.
  if (!isObject(parsed)) throw new Error(`corrupt config ${file}: expected a JSON object`)
  return parsed
}

// Compared on the live keys only: a stored entry may also carry a retired field.
const differs = (stored, live) =>
  Object.entries(live).some(([k, v]) => JSON.stringify(stored[k]) !== JSON.stringify(v))

function saveConfig(staticVer, flat) {
  const file = configPath(staticVer)
  const config = loadConfig(staticVer)

  // A version means one set of bytes (content-addressed and cached), so a stored
  // entry can never legitimately change -- if it does, either the stored value is
  // wrong or the content was swapped in place. Do not silently overwrite it.
  if (config[staticVer] && differs(config[staticVer], flat)) {
    throw new Error(`stored ${staticVer} disagrees with live: ${JSON.stringify(config[staticVer])} vs ${JSON.stringify(flat)}`)
  }

  // Sorted keys and exactly one trailing newline keep the file canonical and match what
  // prek's end-of-file-fixer would write. Merged over the stored entry so a retired key
  // survives and an unchanged build is not rewritten.
  const merged = { ...config, [staticVer]: { ...config[staticVer], ...flat } }
  const sorted = Object.fromEntries(Object.entries(merged).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)))
  const content = JSON.stringify(sorted, null, 2) + '\n'
  const changed = !existsSync(file) || readFileSync(file, 'utf8') !== content

  if (changed && !dryRun) {
    mkdirSync(CONFIG_DIR, { recursive: true })
    writeFileSync(`${file}.tmp`, content, 'utf8') // temp + rename, never a truncated file
    renameSync(`${file}.tmp`, file)
  }
  return changed
}

const assetCache = new Map()
async function fetchText(url, cached = false) {
  if (cached && assetCache.has(url)) return await assetCache.get(url)

  const pending = (async () => {
    let lastError
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const res = await fetch(url, { signal: AbortSignal.timeout(15_000) })
        if (res.ok) return await res.text()
        lastError = new Error(`HTTP ${res.status} for ${url}`)
        if (res.status < 500 && res.status !== 429) break // 4xx won't fix itself
      } catch (e) {
        lastError = e
      }
    }
    throw lastError
  })()

  if (cached) {
    assetCache.set(url, pending)
    pending.catch(() => assetCache.delete(url)) // let a later site retry
  }
  return await pending
}

function only(value, label) {
  const entries = isObject(value) ? Object.entries(value) : []
  if (entries.length !== 1) {
    throw new Error(`Failed to extract ${label}: expected 1 entry, got ${entries.length} (${JSON.stringify(value)})`)
  }
  return entries[0]
}

// The SDK writes `_lib` and `lib._abo` in its opening statement, then dies on `window`, so
// `lib` is the only global it needs. Since v1.9.8 an env honeypot rewrites `_abo` to a bot
// marker once it thinks the runtime is Node or a DOM shim; with no `window` that probe never
// runs, and if it ever does the second write throws instead of silently picking one.
const SANDBOX_BOOTSTRAP = `(function () {
  var g = globalThis;
  var store = {};
  var lib = {};
  Object.defineProperty(lib, '_abo', {
    configurable: true,
    enumerable: true,
    get: function () { return store._abo; },
    set: function (value) {
      if (Object.prototype.hasOwnProperty.call(store, '_abo'))
        throw new Error('lib._abo written twice: ' + JSON.stringify(value));
      store._abo = value;
    },
  });
  g.lib = lib;
})()`

function runInSandbox(sdkSource, gctSource) {
  if (!vm.constants?.DONT_CONTEXTIFY)
    throw new Error('needs node >= 22.8: without vm.constants.DONT_CONTEXTIFY the host realm leaks in through globalThis.constructor')

  const ctx = vm.createContext(vm.constants.DONT_CONTEXTIFY)
  vm.runInContext(SANDBOX_BOOTSTRAP, ctx)

  let sdkError
  try {
    vm.runInContext(sdkSource, ctx, { timeout: 5_000 })
  } catch (e) {
    // Dies on `window` right after the prologue -- unless the guard fired, which is not ours
    // to swallow: a rewritten `_abo` means the honeypot ran and the build needs a human.
    if (/^lib\._abo written twice/.test(e?.message ?? ''))
      throw new Error(`SDK rewrote lib._abo -- env honeypot fired, refusing to guess: ${e.message}`)
    sdkError = e
  }

  // Read out as a JSON string -- no host value crosses the realm line.
  const seen = readJson(ctx, `({
    lib: globalThis._lib || null,
    abo: (globalThis.lib && globalThis.lib._abo) || null,
  })`)
  if (!seen.lib || !seen.abo)
    throw new Error(`Failed to run SDK script: ${sdkError?.message ?? 'no lib/abo was written'}`)

  // `_gct` takes an object; build it inside rather than passing one in.
  const gctCtx = vm.createContext(vm.constants.DONT_CONTEXTIFY)
  vm.runInContext(gctSource, gctCtx, { timeout: 5_000 })
  const gct = readJson(gctCtx, `(function () {
    var o = { lang: 'zh', ep: '123' };
    _gct(o);
    return o;
  })()`)

  return { ...seen, biht: gct.biht }
}

function readJson(context, expression) {
  return JSON.parse(vm.runInContext(`JSON.stringify(${expression})`, context))
}

// The SDK is remote code, so it runs in a child under --permission, with an empty env and
// the source fed over stdin. Windows cannot narrow --allow-fs-read (the module resolver
// walks past it), so it is `*` there; write and exec stay blocked on every platform.
function extractFlat(sdkSource, gctSource) {
  const child = spawnSync(
    process.execPath,
    ['--permission', '--allow-fs-read=*', fileURLToPath(import.meta.url), '--sandbox'],
    {
      input: JSON.stringify({ sdk: sdkSource, gct: gctSource }),
      env: process.platform === 'win32' ? { SystemRoot: process.env.SystemRoot } : {},
      timeout: 30_000,
      maxBuffer: 8 * 1024 * 1024,
      encoding: 'utf8',
    },
  )
  if (child.error) throw new Error(`sandbox child failed: ${child.error.message}`)
  if (child.status !== 0)
    throw new Error(`sandbox child exited ${child.status}: ${(child.stderr || '').trim().slice(0, 400)}`)

  // The child prints exactly one line, so a newline means something else wrote to stdout.
  if (/[\r\n]/.test(child.stdout))
    throw new Error(`sandbox child wrote more than the result line: ${JSON.stringify(child.stdout.slice(0, 200))}`)

  const seen = JSON.parse(child.stdout)
  const [lib_key, lib_val] = only(seen.lib, 'lib')
  const [abo_key, abo_val] = only(seen.abo, 'abo')

  // Canary for the value above: the declared pair sits in the file prologue, so the first
  // 2 KB must contain it. A wrong abo fails every solve, so refuse to write it.
  const prologue = sdkSource.slice(0, 2_000).replace(/["']/g, '')
  if (prologue.includes('._abo') && !(prologue.includes(abo_key) && prologue.includes(abo_val)))
    throw new Error(`kept abo ${abo_key}/${abo_val} is not the one declared in the SDK prologue`)

  const flat = { biht: seen.biht, lib_key, lib_val, abo_key, abo_val }

  for (const [k, v] of Object.entries(flat)) {
    if (v === undefined || v === null || v === '')
      throw new Error(`Failed to extract ${k}: got ${JSON.stringify(v)}`)
  }
  return flat
}

async function extractSite(captcha_id) {
  const query = new URLSearchParams({
    captcha_id,
    challenge: randomUUID(),
    client_type: 'web',
    risk_type: 'ai',
    lang: 'zh',
    callback: `geetest_${Date.now()}`,
  })

  const text = await fetchText(`${GCAPTCHA_BASE}/load?${query}`)
  const m = text.match(/geetest_\d+\(([\s\S]*)\)/)
  if (!m) throw new Error(`unparsable load response: ${text.slice(0, 120)}`)

  const { gct_path, static_path, js } = JSON.parse(m[1]).data ?? {}
  // static_path ends up in a file name, so reject anything that could escape CONFIG_DIR.
  const prefix = '/v4/static/'
  const staticVer = typeof static_path === 'string' && static_path.startsWith(prefix) ? static_path.slice(prefix.length) : ''
  if (!/^[0-9A-Za-z][0-9A-Za-z.-]*$/.test(staticVer) || staticVer.includes('..')) {
    throw new Error(`unsafe static_path: ${JSON.stringify(static_path)}`)
  }

  const [sdkSource, gctSource] = await Promise.all([
    localFile ? readFile(localFile, 'utf8') : fetchText(STATIC_BASE + static_path + js, true),
    fetchText(STATIC_BASE + gct_path, true),
  ])
  return { captcha_id, staticVer, gctPath: gct_path, flat: extractFlat(sdkSource, gctSource) }
}

// Child mode: the only thing it does is run the two sources and print one JSON line.
if (process.argv.includes('--sandbox')) {
  const chunks = []
  for await (const chunk of process.stdin) chunks.push(chunk)
  const { sdk, gct } = JSON.parse(Buffer.concat(chunks).toString('utf8'))
  const out = JSON.stringify(runInSandbox(sdk, gct))
  await new Promise((resolve) => process.stdout.write(out, resolve))
  process.exit(0)
}

const results = []
for (const [i, captcha_id] of CAPTCHA_IDS.entries()) {
  try {
    const r = await extractSite(captcha_id)
    results.push(r)
    console.log(`[${i + 1}/${CAPTCHA_IDS.length}] ${captcha_id.slice(0, 8)} -> ${r.staticVer} lib=${r.flat.lib_key}/${r.flat.lib_val}`)
  } catch (e) {
    warn(`${captcha_id}: ${e.message}`)
  }
}
// Any single failure fails the job. A site that silently drops out would leave the others
// succeeding on their own, so a honeypot trip on the build it was serving would go unseen.
const failed = CAPTCHA_IDS.length - results.length
if (failed) throw new Error(`${failed} of ${CAPTCHA_IDS.length} site(s) failed to extract, see the [warn] lines above`)

// One static_path can only ever serve one set of bytes (content-addressed and
// cached), so sites sharing a build must agree. A mismatch means the extraction
// broke or the response was tampered with -- there is nothing to wait out.
const byVersion = new Map()
for (const r of results) {
  const seen = byVersion.get(r.staticVer)
  if (seen && differs(seen.flat, r.flat)) {
    throw new Error(`sites disagree on the same build ${r.staticVer}: ${JSON.stringify(seen.flat)} vs ${JSON.stringify(r.flat)}`)
  }
  if (seen) seen.sites++
  else byVersion.set(r.staticVer, { flat: r.flat, sites: 1 })
}

if (new Set(results.map((r) => r.gctPath)).size > 1) {
  // Not an error: a different gct path is a different version, same as a
  // different static path. gct_path has been stable for years, so `biht` is
  // compared per static version rather than split onto its own gct key.
  warn(`gct_path differs across sites: ${[...new Set(results.map((r) => r.gctPath))].join(' | ')}`)
}

let changed = false
const changedVersions = []
for (const [staticVer, { flat, sites }] of byVersion) {
  const isChanged = saveConfig(staticVer, flat)
  changed ||= isChanged
  if (isChanged) changedVersions.push(staticVer)
  const display = path.relative(process.cwd(), configPath(staticVer))
  console.log(`${isChanged ? (dryRun ? 'would update' : 'updated') : 'no changes'} ${staticVer} (${sites} site${sites > 1 ? 's' : ''}) -> ${display}`)
}

if (process.env.GITHUB_OUTPUT) {
  appendFileSync(process.env.GITHUB_OUTPUT, `GEETEST_VER=${changedVersions.join(', ')}\nCHANGED=${changed}\n`)
}
