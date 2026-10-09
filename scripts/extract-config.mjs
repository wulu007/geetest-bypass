import { randomUUID } from 'node:crypto'
import { appendFileSync, existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const GCAPTCHA_BASE = 'https://gcaptcha4.geetest.com'
const STATIC_BASE = 'https://static.geetest.com'
const CONFIG_DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'wulu_geetest_bypass', 'data')

// Probing several sites because one can be pinned to a stale (or ahead-of-fleet)
// build. Deduped: a repeated id would fake the cross-check below.
const CAPTCHA_IDS = [...new Set([
  '24f56dc13c40dc4a02fd0318567caef5', // geetest demo
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

// Order-independent, unlike stringifying the whole object.
const differs = (a, b) =>
  Object.keys(a).length !== Object.keys(b).length ||
  Object.entries(a).some(([k, v]) => JSON.stringify(v) !== JSON.stringify(b[k]))

function saveConfig(staticVer, flat) {
  const file = configPath(staticVer)
  const config = loadConfig(staticVer)

  // A version means one set of bytes (content-addressed and cached), so a stored
  // entry can never legitimately change -- if it does, either the stored value is
  // wrong or the content was swapped in place. Do not silently overwrite it.
  if (config[staticVer] && differs(config[staticVer], flat)) {
    throw new Error(`stored ${staticVer} disagrees with live: ${JSON.stringify(config[staticVer])} vs ${JSON.stringify(flat)}`)
  }

  // Sorted keys and exactly one trailing newline keep the file canonical and
  // match what prek's end-of-file-fixer would write.
  const merged = { ...config, [staticVer]: flat }
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

function extractFlat(sdkSource, gctSource) {
  // window/self/globalThis point back at the sandbox object: pointing window at
  // the real global would hand remote code window.process (node:vm is not a sandbox).
  const ctx = {
    document: { getElementsByTagName: () => [], createElement: () => Object() },
    lib: {},
    location: {},
    navigator: globalThis.navigator,
    setTimeout: () => { },
    global: null,
  }
  ctx.window = ctx.self = ctx.globalThis = ctx

  const track = randomUUID()
  vm.createContext(ctx)
  try {
    vm.runInContext(
      `Object.defineProperty(Object.prototype, 'appendTrack', { set() { globalThis['${track}'] = true }, configurable: true })`,
      ctx,
    )
    vm.runInContext(sdkSource, ctx, { timeout: 5_000 })
  } catch (e) {
    if (ctx[track] === undefined) throw new Error(`Failed to run SDK script: ${e.message}`)
  }
  if (ctx[track] === undefined) ctx[track] = false

  const gctCtx = {}
  vm.createContext(gctCtx)
  vm.runInContext(gctSource, gctCtx, { timeout: 5_000 })
  const obj = { lang: 'zh', ep: '123' }
  gctCtx._gct(obj)

  const [lib_key, lib_val] = only(ctx._lib, 'lib')
  const [abo_key, abo_val] = only(ctx.lib && ctx.lib._abo, 'abo')
  const flat = { biht: obj.biht, lib_key, lib_val, abo_key, abo_val, track_enable: ctx[track] }

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

const results = []
for (const [i, captcha_id] of CAPTCHA_IDS.entries()) {
  try {
    const r = await extractSite(captcha_id)
    results.push(r)
    console.log(`[${i + 1}/${CAPTCHA_IDS.length}] ${captcha_id.slice(0, 8)} -> ${r.staticVer} lib=${r.flat.lib_key}/${r.flat.lib_val} track=${r.flat.track_enable}`)
  } catch (e) {
    warn(`${captcha_id}: ${e.message}`)
  }
}
if (!results.length) throw new Error(`all ${CAPTCHA_IDS.length} captcha_id(s) failed to extract`)

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
