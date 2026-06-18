import { randomUUID } from 'node:crypto'
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

const res = await fetch(`${GCAPTCHA_BASE}/load?${new URLSearchParams(params)}`)
if (!res.ok) throw new Error(`load API HTTP ${res.status}`)
const m = (await res.text()).match(/geetest_\d+\(([\s\S]*)\)/)
const { gct_path, static_path, js } = JSON.parse(m[1]).data

const [sdkSource, gctSource] = await Promise.all([
  fetch(STATIC_BASE + static_path + js).then(r => r.text()),
  fetch(STATIC_BASE + gct_path).then(r => r.text()),
])

const sdkCtx = { self: null, global: null, globalThis: null, lib: {}, console: { log: () => { }, error: () => { } } }
sdkCtx.self = sdkCtx; sdkCtx.global = sdkCtx; sdkCtx.globalThis = sdkCtx
vm.createContext(sdkCtx)
try {
  vm.runInContext(sdkSource, sdkCtx, { timeout: 5000 })
} catch { }

const gctCtx = {}
vm.createContext(gctCtx)
vm.runInContext(gctSource, gctCtx)
const obj = { lang: 'zh', ep: '123' }
gctCtx._gct(obj)

console.log(`biht=${obj.biht}`)
console.log(`static_ver=${static_path.replace('/v4/static/', '')}`)
if (sdkCtx._lib) {
  for (const [k, v] of Object.entries(sdkCtx._lib)) {
    console.log(`lib_key=${k}`)
    console.log(`lib_val=${v}`)
  }
}
if (sdkCtx.lib && sdkCtx.lib._abo) {
  for (const [k, v] of Object.entries(sdkCtx.lib._abo)) {
    console.log(`abo_key=${k}`)
    console.log(`abo_val=${v}`)
  }
}
