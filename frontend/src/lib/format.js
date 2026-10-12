// Small display helpers shared by several pages.

export const formatCost = (usd) =>
  usd == null ? null : usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(3)}`

export const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`

export const formatTime = (iso) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })

export const formatBytes = (bytes) =>
  bytes < 1024 ? `${bytes} B` : bytes < 1024 ** 2 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`
