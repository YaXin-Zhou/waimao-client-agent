const API_BASE = 'http://127.0.0.1:8002'
const ALARM_NAME = 'northstar-search-fallback'

async function ensureMonitor() {
  const alarm = await chrome.alarms.get(ALARM_NAME)
  if (!alarm) chrome.alarms.create(ALARM_NAME, { periodInMinutes: 0.5 })
}

async function readJson(url) {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`local API ${response.status}`)
  return response.json()
}

function buildSearchUrl(task) {
  const criteria = task?.criteria || {}
  const values = [
    criteria.product,
    ...(Array.isArray(criteria.keywords) ? criteria.keywords : []),
    ...(Array.isArray(criteria.industries) ? criteria.industries : []),
    ...(Array.isArray(criteria.countries) ? criteria.countries : [])
  ].flatMap((value) => String(value || '').split(/[,，、;；|/]/)).map((value) => value.trim()).filter(Boolean)
  return `https://www.google.com/search?q=${encodeURIComponent([...new Set(values)].join(' '))}`
}

async function monitorSearchRun() {
  try {
    const tasksPayload = await readJson(`${API_BASE}/api/tasks`)
    const task = tasksPayload.items?.[0]
    if (!task?.id) return
    const runsPayload = await readJson(`${API_BASE}/api/tasks/${encodeURIComponent(task.id)}/discovery-runs`)
    // The API returns runs in creation order. The newest run must be used;
    // reading item 0 would keep the extension pinned to the first historical
    // run and make later failures invisible.
    const latest = runsPayload.items?.at(-1)
    if (!latest?.id) return
    const signature = `${latest.id}:${latest.status}`
    const state = await chrome.storage.local.get('lastDiscoverySignature')
    if (!state.lastDiscoverySignature) {
      await chrome.storage.local.set({ lastDiscoverySignature: signature })
      return
    }
    if (state.lastDiscoverySignature === signature) return
    await chrome.storage.local.set({ lastDiscoverySignature: signature })
    // A search can technically succeed while producing no qualified customer
    // (for example, it found a website but no acceptable public mailbox). In
    // that case the browser is still the intended second chance.
    const needsFallback = latest.status === 'failed'
      || latest.status === 'succeeded' && Number(latest.qualified_count || 0) === 0
    if (!needsFallback) return
    // Make the fallback visible so the user can see that the second search
    // source has started. The extension still opens only one tab per run.
    await chrome.tabs.create({ url: buildSearchUrl(task), active: true })
  } catch {
    // The local app may be closed; retry on the next alarm without surfacing
    // an extension error to the customer.
  }
}

chrome.runtime.onInstalled.addListener(() => {
  ensureMonitor()
  monitorSearchRun()
})

chrome.runtime.onStartup.addListener(() => {
  ensureMonitor()
  monitorSearchRun()
})

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) monitorSearchRun()
})

// Reloading an unpacked extension does not always fire onInstalled. The
// top-level recovery makes the monitor self-healing whenever Chrome wakes the
// service worker, so customers do not need to configure a timer manually.
ensureMonitor()
  .then(() => monitorSearchRun())
  .catch(() => {})
