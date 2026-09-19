import { randomUUID } from 'node:crypto'
import { existsSync } from 'node:fs'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const GCAPTCHA_BASE = 'https://gcaptcha4.geetest.com'
const STATIC_BASE = 'https://static.geetest.com'

const params = {
  captcha_id: '24f56dc13c40dc4a02fd0318567caef5',
  challenge: randomUUID(),
  client_type: 'web',
  risk_type: 'ai',
  lang: 'zh',
  callback: `geetest_${Date.now()}`,
}

const localFile = process.argv[2] || null
async function loadScript(remotePath) {
  if (localFile) {
    if (existsSync(localFile)) {
      return await readFile(localFile, 'utf8')
    }
  }
  const url = STATIC_BASE + remotePath
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`)
  return await res.text()
}

const res = await fetch(`${GCAPTCHA_BASE}/load?${new URLSearchParams(params)}`)
if (!res.ok) throw new Error(`load API HTTP ${res.status}`)
const m = (await res.text()).match(/geetest_\d+\(([\s\S]*)\)/)
const { gct_path, static_path, js } = JSON.parse(m[1]).data

const [sdkSource, gctSource] = await Promise.all([
  loadScript(static_path + js),
  fetch(STATIC_BASE + gct_path).then(r => r.text()),
])

globalThis.document = {
  getElementsByTagName: () => [],
  createElement: () => Object()
}
globalThis.location = {}
const sdkCtx = {
  window: globalThis,
  document: globalThis.document,
  self: globalThis, global: null, globalThis: globalThis, lib: {},
  navigator: globalThis.navigator,
  setTimeout: () => { }
}
sdkCtx.self = sdkCtx.globalThis = sdkCtx;
const track_enable = randomUUID()
vm.createContext(sdkCtx)
try {
  vm.runInContext(`
    Object.defineProperty(Object.prototype, 'appendTrack', {
      set: function () {
        globalThis['${track_enable}'] = true
      },
      configurable: true
    })
  `, sdkCtx)
  vm.runInContext(sdkSource, sdkCtx, { timeout: 5000 })
  if (sdkCtx[track_enable] === undefined)
    sdkCtx[track_enable] = false
} catch (e) {
  if (sdkCtx[track_enable] === undefined)
    throw new Error(`Failed to run SDK script: ${e.message}`)
}

const gctCtx = {}
vm.createContext(gctCtx)
vm.runInContext(gctSource, gctCtx)
const obj = { lang: 'zh', ep: '123' }
gctCtx._gct(obj)

function pickSingleEntries(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`Failed to extract ${label}: expected a non-empty object, got ${JSON.stringify(value)}`)
  }
  const entries = Object.entries(value)
  if (entries.length !== 1) {
    throw new Error(`Failed to extract ${label}: expected exactly 1 entry, got ${entries.length} (${JSON.stringify(value)})`)
  }
  return entries[0]
}

function requireStaticVer(staticPath) {
  const prefix = '/v4/static/'
  if (typeof staticPath !== 'string' || !staticPath.startsWith(prefix)) {
    throw new Error(`Failed to extract static_ver: unexpected static_path ${JSON.stringify(staticPath)}`)
  }
  const ver = staticPath.slice(prefix.length)
  if (!ver) {
    throw new Error(`Failed to extract static_ver: empty version in static_path ${JSON.stringify(staticPath)}`)
  }
  return ver
}

const [lib_key, lib_val] = pickSingleEntries(sdkCtx._lib, 'lib')
const [abo_key, abo_val] = pickSingleEntries(sdkCtx.lib && sdkCtx.lib._abo, 'abo')

const flat = {
  biht: obj.biht,
  static_ver: requireStaticVer(static_path),
  lib_key,
  lib_val,
  abo_key,
  abo_val,
  track_enable: sdkCtx[track_enable],
}

for (const [k, v] of Object.entries(flat)) {
  if (v === undefined || v === null || v === '') {
    throw new Error(`Failed to extract ${k}: got ${JSON.stringify(v)}`)
  }
}

console.log(JSON.stringify(flat, null, 2))
