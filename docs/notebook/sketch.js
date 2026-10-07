// Tiny diagram helper on top of rough.js: hand-drawn boxes, cylinders, arrows,
// text and sequence diagrams as crisp vector SVG (stays sharp in the PDF).
//
// Usage inside notebook.html, right after an <svg id="d-something"></svg>:
//   sketch("d-something", 680, 300, (d) => {
//     const a = d.box(20, 20, 140, 60, "React UI", { fill: "blue" })
//     const b = d.box(300, 20, 140, 60, "FastAPI", { fill: "green" })
//     d.arrow(a.right, b.left, { label: "REST" })
//   })
// Seeds are derived from the svg id, so every rebuild draws identical wobbles.

const NS = "http://www.w3.org/2000/svg"
const PEN = {
  ink: "#1b2740",
  blue: "#1f4fbf",
  red: "#c62828",
  green: "#2e7d32",
  orange: "#c96a00",
  purple: "#6b3fa0",
  gray: "#6b7585",
  white: "#ffffff",
}
const FILL = {
  blue: "#bcd3ff",
  yellow: "#ffe873",
  green: "#bfe8b8",
  pink: "#ffc4cf",
  purple: "#dccbff",
  orange: "#ffd29c",
  gray: "#e2e5ea",
  white: "#ffffff",
  paper: "#fffdf7",
}
const FONTS = {
  hand: "Patrick Hand",
  title: "Caveat",
  bold: "Kalam",
}

function seedFrom(text) {
  let h = 17
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) % 2147483647
  return h || 1
}

function sketch(id, width, height, draw) {
  const svg = document.getElementById(id)
  if (!svg) throw new Error(`sketch: no <svg id="${id}">`)
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`)
  svg.setAttribute("xmlns", NS)
  const rc = rough.svg(svg, {
    options: { seed: seedFrom(id), roughness: 1.05, bowing: 1, stroke: PEN.ink, strokeWidth: 1.6 },
  })
  const add = (node) => (svg.appendChild(node), node)
  const pen = (c) => PEN[c] ?? c ?? PEN.ink
  const fill = (c) => (c ? FILL[c] ?? c : undefined)

  function text(x, y, str, o = {}) {
    const { size = 17, color = "ink", anchor = "middle", font = "hand", weight = 400, rotate = 0 } = o
    const t = document.createElementNS(NS, "text")
    t.setAttribute("x", x)
    t.setAttribute("y", y)
    t.setAttribute("text-anchor", anchor)
    t.setAttribute("dominant-baseline", "central")
    t.setAttribute("font-family", FONTS[font] ?? font)
    t.setAttribute("font-size", size)
    t.setAttribute("font-weight", weight)
    t.setAttribute("fill", pen(color))
    if (rotate) t.setAttribute("transform", `rotate(${rotate} ${x} ${y})`)
    const lines = String(str).split("\n")
    const lh = size * 1.13
    lines.forEach((line, i) => {
      const span = document.createElementNS(NS, "tspan")
      span.setAttribute("x", x)
      span.setAttribute("dy", i === 0 ? -((lines.length - 1) * lh) / 2 : lh)
      span.textContent = line
      t.appendChild(span)
    })
    return add(t)
  }

  function shapeOpts(o) {
    const opts = {
      stroke: pen(o.color),
      strokeWidth: o.strokeWidth ?? 1.6,
      fill: fill(o.fill),
      fillStyle: o.fillStyle ?? "hachure",
      hachureGap: o.hachureGap ?? 4.2,
      fillWeight: o.fillWeight ?? 1.1,
      hachureAngle: o.hachureAngle ?? -41,
    }
    if (o.dashed) opts.strokeLineDash = [7, 6]
    return opts
  }

  function anchors(x, y, w, h) {
    return {
      x, y, w, h,
      cx: x + w / 2,
      cy: y + h / 2,
      top: [x + w / 2, y],
      bottom: [x + w / 2, y + h],
      left: [x, y + h / 2],
      right: [x + w, y + h / 2],
      at: (fx, fy) => [x + w * fx, y + h * fy],
    }
  }

  // shape: rect | ellipse | db | diamond | cloud | note
  function box(x, y, w, h, label, o = {}) {
    const opts = shapeOpts(o)
    const shape = o.shape ?? "rect"
    if (shape === "ellipse") add(rc.ellipse(x + w / 2, y + h / 2, w, h, opts))
    else if (shape === "diamond")
      add(rc.polygon([[x + w / 2, y], [x + w, y + h / 2], [x + w / 2, y + h], [x, y + h / 2]], opts))
    else if (shape === "db") {
      const ry = Math.min(11, h * 0.16)
      add(rc.path(`M ${x} ${y + ry} L ${x} ${y + h - ry} A ${w / 2} ${ry} 0 0 0 ${x + w} ${y + h - ry} L ${x + w} ${y + ry}`, opts))
      add(rc.ellipse(x + w / 2, y + ry, w, ry * 2, { ...opts, fillStyle: "solid", fill: fill(o.fill) ?? FILL.paper }))
    } else if (shape === "cloud") {
      const r = h / 2
      add(rc.path(
        `M ${x + r} ${y + h} ` +
          `C ${x - r * 0.4} ${y + h} ${x - r * 0.3} ${y + h * 0.35} ${x + r * 0.7} ${y + h * 0.3} ` +
          `C ${x + r * 0.9} ${y - h * 0.15} ${x + w * 0.55} ${y - h * 0.15} ${x + w * 0.62} ${y + h * 0.18} ` +
          `C ${x + w * 0.8} ${y - h * 0.05} ${x + w + r * 0.25} ${y + h * 0.3} ${x + w - r * 0.35} ${y + h * 0.62} ` +
          `C ${x + w + r * 0.2} ${y + h * 1.05} ${x + w * 0.8} ${y + h * 1.1} ${x + w * 0.7} ${y + h} Z`,
        opts,
      ))
    } else if (shape === "note") {
      add(rc.rectangle(x, y, w, h, { ...opts, fill: fill(o.fill ?? "yellow"), fillStyle: "solid", stroke: "none" }))
      add(rc.line(x, y + h, x + w, y + h, { stroke: pen("gray"), strokeWidth: 1 }))
    } else add(rc.rectangle(x, y, w, h, opts))

    const size = o.size ?? 17
    const yShift = shape === "db" ? 7 : 0
    const cy = y + h / 2 + yShift
    if (label != null) {
      const subLines = o.sub ? String(o.sub).split("\n").length : 0
      const labelY = o.sub ? cy - (subLines * (size - 3) * 1.13) / 2 : cy
      text(x + w / 2, labelY, label, {
        size, font: o.font ?? "hand", weight: o.weight ?? 400, color: o.textColor ?? "ink",
      })
      if (o.sub) {
        const labelLines = String(label).split("\n").length
        text(x + w / 2, labelY + ((labelLines + subLines) * size * 1.13) / 2, o.sub, {
          size: size - 3, color: o.subColor ?? "gray",
        })
      }
    }
    return anchors(x, y, w, h)
  }

  function head(fromX, fromY, x, y, opts, len = 11) {
    const angle = Math.atan2(y - fromY, x - fromX)
    const spread = 0.45
    add(rc.line(x, y, x - len * Math.cos(angle - spread), y - len * Math.sin(angle - spread), opts))
    add(rc.line(x, y, x - len * Math.cos(angle + spread), y - len * Math.sin(angle + spread), opts))
  }

  // from/to are [x, y]. bend > 0 curves the arrow to its left.
  function arrow(from, to, o = {}) {
    const [x1, y1] = from
    const [x2, y2] = to
    const opts = { stroke: pen(o.color), strokeWidth: o.width ?? 1.5, roughness: 0.9 }
    if (o.dashed) opts.strokeLineDash = [6, 5]
    let midX = (x1 + x2) / 2
    let midY = (y1 + y2) / 2
    let tailRef = [x2, y2]
    let headRef = [x1, y1]
    if (o.bend) {
      const dx = x2 - x1
      const dy = y2 - y1
      const len = Math.hypot(dx, dy) || 1
      midX -= (dy / len) * o.bend
      midY += (dx / len) * o.bend
      add(rc.curve([[x1, y1], [midX, midY], [x2, y2]], opts))
      headRef = [midX, midY]
      tailRef = [midX, midY]
    } else add(rc.line(x1, y1, x2, y2, opts))
    if (!o.noHead) head(headRef[0], headRef[1], x2, y2, opts)
    if (o.both) head(tailRef[0], tailRef[1], x1, y1, opts)
    if (o.label) {
      const [ox, oy] = o.labelOffset ?? [0, -11]
      text(midX + ox, midY + oy, o.label, { size: o.size ?? 15, color: o.labelColor ?? o.color ?? "ink" })
    }
  }

  // Polyline through points, arrow head at the end.
  function path(points, o = {}) {
    const opts = { stroke: pen(o.color), strokeWidth: o.width ?? 1.5, roughness: 0.9 }
    if (o.dashed) opts.strokeLineDash = [6, 5]
    add(rc.linearPath(points, opts))
    const n = points.length
    if (!o.noHead) head(points[n - 2][0], points[n - 2][1], points[n - 1][0], points[n - 1][1], opts)
    if (o.label) {
      const [lx, ly] = o.labelAt ?? points[Math.floor(n / 2)]
      text(lx, ly, o.label, { size: o.size ?? 15, color: o.labelColor ?? o.color ?? "ink" })
    }
  }

  function line(x1, y1, x2, y2, o = {}) {
    const opts = { stroke: pen(o.color), strokeWidth: o.width ?? 1.4, roughness: o.roughness ?? 0.9 }
    if (o.dashed) opts.strokeLineDash = [6, 5]
    add(rc.line(x1, y1, x2, y2, opts))
  }

  function circle(cx, cy, d, o = {}) {
    add(rc.circle(cx, cy, d, shapeOpts(o)))
    if (o.label != null) text(cx, cy, o.label, { size: o.size ?? 16, color: o.textColor ?? "ink", font: o.font ?? "hand" })
    return anchors(cx - d / 2, cy - d / 2, d, d)
  }

  function check(x, y, o = {}) {
    const opts = { stroke: pen(o.color ?? "green"), strokeWidth: o.width ?? 2.4, roughness: 0.6 }
    add(rc.linearPath([[x - 7, y], [x - 2, y + 6], [x + 9, y - 8]], opts))
  }

  function cross(x, y, o = {}) {
    const opts = { stroke: pen(o.color ?? "red"), strokeWidth: o.width ?? 2.4, roughness: 0.6 }
    add(rc.line(x - 7, y - 7, x + 7, y + 7, opts))
    add(rc.line(x + 7, y - 7, x - 7, y + 7, opts))
  }

  // Bar chart with hand-drawn bars: data = [{label, value, color}]
  function bars(x, y, w, h, data, o = {}) {
    const max = o.max ?? Math.max(...data.map((d) => d.value))
    const gap = o.gap ?? 10
    const bw = (w - gap * (data.length - 1)) / data.length
    line(x - 4, y + h, x + w + 4, y + h, { width: 1.6 })
    data.forEach((d, i) => {
      const bh = (d.value / max) * (h - 18)
      const bx = x + i * (bw + gap)
      box(bx, y + h - bh, bw, bh, null, { fill: d.color ?? "blue", hachureGap: 3.5 })
      text(bx + bw / 2, y + h - bh - 9, d.top ?? "", { size: 13, color: "gray" })
      text(bx + bw / 2, y + h + 11, d.label, { size: o.labelSize ?? 13 })
    })
  }

  // Sequence diagram. actors: [{id, label, fill}], steps:
  //   {from, to, label, reply?, color?}  or  {self: id, label}  or  {note, at?}
  function sequence({ actors, steps, top = 4, actorW = 116, actorH = 40, gap = 31, left = 8, right }) {
    const usable = (right ?? width - 8) - left - actorW
    const span = actors.length > 1 ? usable / (actors.length - 1) : 0
    const xs = {}
    actors.forEach((a, i) => {
      const cx = left + actorW / 2 + i * span
      xs[a.id] = cx
      box(cx - actorW / 2, top, actorW, actorH, a.label, { fill: a.fill ?? "blue", size: a.size ?? 16 })
    })
    const startY = top + actorH + 24
    const bottom = startY + (steps.length - 1) * gap + 16
    actors.forEach((a) => line(xs[a.id], top + actorH, xs[a.id], bottom, { color: "gray", dashed: true, width: 1 }))
    steps.forEach((s, i) => {
      const y = startY + i * gap
      if (s.note) {
        text(s.at ? xs[s.at] : (left + (right ?? width - 8)) / 2, y, s.note, {
          size: s.size ?? 15, color: s.color ?? "purple", font: "title", weight: 700,
        })
        return
      }
      if (s.self) {
        const x = xs[s.self]
        const opts = { stroke: pen(s.color), strokeWidth: 1.4 }
        add(rc.linearPath([[x + 3, y - 9], [x + 30, y - 9], [x + 30, y + 7], [x + 5, y + 7]], opts))
        head(x + 30, y + 7, x + 4, y + 7, opts, 9)
        text(x + 36, y - 1, s.label, { size: s.size ?? 14.5, anchor: "start", color: s.color ?? "ink" })
        return
      }
      const xa = xs[s.from]
      const xb = xs[s.to]
      const dir = Math.sign(xb - xa)
      arrow([xa + dir * 3, y], [xb - dir * 3, y], {
        label: s.label, dashed: s.reply, color: s.color, size: s.size ?? 14.5, labelOffset: [0, -10],
      })
    })
    return bottom
  }

  draw({ box, arrow, path, line, text, circle, check, cross, bars, sequence, width, height, PEN, FILL })
}
