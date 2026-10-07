// Builds the notebook PDF with a locally installed Chrome/Edge (no npm packages needed).
//
//   node docs/notebook/build.mjs             -> docs/notebook/SQLAssist-Notebook.pdf
//   node docs/notebook/build.mjs --check     -> lists pages whose content overflows the A4 sheet
//   node docs/notebook/build.mjs --png 3,12  -> PNG previews of single pages (in your temp folder)
//
// Fonts (Google Fonts) and rough.js (jsDelivr) are fetched at build time, so you need internet.

import { execFileSync } from "node:child_process"
import { existsSync, mkdirSync } from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const here = dirname(fileURLToPath(import.meta.url))
const source = join(here, "notebook.html")
const output = join(here, "SQLAssist-Notebook.pdf")

const browser = [
  process.env.CHROME_PATH,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
]
  .filter(Boolean)
  .find(existsSync)

if (!browser) {
  console.error("No Chrome/Edge found. Set CHROME_PATH to your browser executable.")
  process.exit(1)
}

const checkOnly = process.argv.includes("--check")
const url = pathToFileURL(source).href + (checkOnly ? "?check" : "")
const flags = [
  "--headless=new",
  "--disable-gpu",
  "--hide-scrollbars",
  // Virtual time pauses while fonts/scripts are still downloading, then lets
  // the page's scripts (diagrams, overflow check) finish before capture.
  "--virtual-time-budget=30000",
  "--run-all-compositor-stages-before-draw",
]

const pngIndex = process.argv.indexOf("--png")
if (pngIndex !== -1) {
  const outDir = join(tmpdir(), "sqlassist-notebook")
  mkdirSync(outDir, { recursive: true })
  for (const page of process.argv[pngIndex + 1].split(",")) {
    const file = join(outDir, `page-${page}.png`)
    execFileSync(browser, [...flags, "--window-size=794,1123", `--screenshot=${file}`,
      `${pathToFileURL(source).href}?only=${page}`], { stdio: "ignore" })
    console.log(file)
  }
  process.exit(0)
}

if (checkOnly) {
  const dom = execFileSync(browser, [...flags, "--dump-dom", url], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  })
  const pages = (dom.match(/<section class="page[ "]/g) ?? []).length
  const overflow = dom.match(/data-overflow="([^"]*)"/)?.[1]
  if (overflow === undefined) {
    console.error("Check script did not run (fonts or scripts failed to load?)")
    process.exit(2)
  }
  console.log(`${pages} pages`)
  console.log(overflow ? `OVERFLOWING pages: ${overflow}` : "No page overflows its sheet.")
  process.exit(overflow ? 1 : 0)
}

execFileSync(browser, [...flags, "--no-pdf-header-footer", `--print-to-pdf=${output}`, url], {
  stdio: "inherit",
})
console.log(`Wrote ${output}`)
