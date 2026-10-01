; (function () {
  // 这两个 key 只在 w 明文里出现，用来把 customTheme 之类的其它调用过滤掉
  var MARKER = ['pow_msg', 'pow_sign']

  var captures = []
  var tracks = []
  var fn = null

  Object.defineProperty(Object.prototype, 'stringify', {
    set: function (val) {
      if (this === Object.prototype) return
      if (typeof val !== 'function') {
        Object.defineProperty(this, 'stringify', {
          value: val,
          writable: true,
          configurable: true,
          enumerable: true,
        })
        return
      }
      if (!fn) {
        fn = val
        console.log('[gt4-hook] 已 hook Object.prototype.stringify')
      }
      var wrapped = function () {
        record(Array.prototype.slice.call(arguments))
        return val.apply(this, arguments)
      }
      Object.defineProperty(this, 'stringify', {
        value: wrapped,
        writable: true,
        configurable: true,
        enumerable: true,
      })
    },
    configurable: true,
  })

  Object.defineProperty(Object.prototype, 'new_track', {
    set: function (val) {
      if (this === Object.prototype) return
      // enumerable 必须为 true：普通赋值建出来的就是可枚举属性，
      // 而 defineProperty 默认 false，会让 for...in 拍不到 new_track
      Object.defineProperty(this, 'new_track', {
        value: val,
        writable: true,
        configurable: true,
        enumerable: true,
      })
      recordTrack(this)
    },
    configurable: true,
  })

  function record(args) {
    var input = args[0]
    if (!input || typeof input !== 'object') return

    var snap = snapshot(input)
    var rec = { input: input, snapshot: snap, args: args, keys: Object.keys(snap), ts: Date.now() }
    captures.push(rec)

    var hit = MARKER.every((m) => m in snap)
    console.log('[gt4-hook] stringify 调用', hit ? '← w 明文载荷' : '', rec.keys.join(','), snap)

    window.dispatchEvent(new CustomEvent('gt4-stringify', { detail: rec }))
    if (hit) window.dispatchEvent(new CustomEvent('gt4-capture', { detail: snap }))
  }

  function recordTrack(owner) {
    var snap = snapshot(owner)
    tracks.push({ owner: owner, snapshot: snap, ts: Date.now() })
    console.log('[gt4-hook] new_track（轨迹归一化）', snap)
    window.dispatchEvent(new CustomEvent('gt4-track', { detail: snap }))
  }

  // 必须用 defineProperty 建副本：直接 out[k] = obj[k] 会命中我们自己装的
  // setter（out 没有自有属性，赋值会走原型链），递归到栈溢出
  function snapshot(obj) {
    var out = {}
    for (var k in obj) {
      if (!Object.prototype.hasOwnProperty.call(obj, k)) continue
      Object.defineProperty(out, k, {
        value: obj[k],
        writable: true,
        enumerable: true,
        configurable: true,
      })
    }
    return out
  }

  window.__gt4Hook = {
    captures: captures,
    tracks: tracks,
    fn: function () {
      return fn
    },
    last: function () {
      return captures[captures.length - 1]
    },
    lastTrack: function () {
      return tracks[tracks.length - 1]
    },
    clear: function () {
      captures.length = 0
      tracks.length = 0
    },
  }
})()
