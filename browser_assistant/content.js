const API_BASE = 'http://127.0.0.1:8002'

function normalized(value) {
  return String(value || '').trim().toLowerCase()
}

function isSearchPage() {
  return window.location.pathname === '/search' && new URLSearchParams(window.location.search).has('q')
}

function currentQuery() {
  return normalized(new URLSearchParams(window.location.search).get('q'))
}

function matchesTask(task) {
  const criteria = task?.criteria || {}
  const query = currentQuery()
  if (!query) return false
  const countries = Array.isArray(criteria.countries) ? criteria.countries : []
  const businessTerms = [criteria.product, ...(Array.isArray(criteria.keywords) ? criteria.keywords : []), ...(Array.isArray(criteria.industries) ? criteria.industries : [])]
    .map(normalized).filter(Boolean)
  const countryMatch = countries.map(normalized).filter(Boolean).some((term) => query.includes(term))
  const businessMatch = businessTerms.some((term) => query.includes(term))
  return countryMatch && businessMatch
}

function extractVisibleResults() {
  const sourceUrl = window.location.href
  const searchHost = window.location.hostname.toLowerCase().replace(/^www\./, '')
  const ignoredHosts = new Set([
    searchHost, 'google.com', 'google.co.uk', 'google.fr', 'google.de', 'google.it', 'google.es',
    'bing.com', 'youtube.com', 'facebook.com', 'linkedin.com', 'wikipedia.org',
    'yelp.com', 'yellowpages.com', 'europages.com', 'inven.com', 'techpilot.com'
  ])
  const seen = new Set()
  const records = []
  for (const anchor of document.querySelectorAll('a[href]')) {
    if (records.length >= 50) break
    let url
    try { url = new URL(anchor.href, sourceUrl) } catch { continue }
    if (!['http:', 'https:'].includes(url.protocol)) continue
    const host = url.hostname.toLowerCase().replace(/^www\./, '')
    // Google and Bing may wrap result links in redirect URLs. Resolve the
    // public target before applying the search-engine and directory filters.
    if (host.endsWith('.google.com') || host.endsWith('.bing.com')) {
      const target = url.searchParams.get('q') || url.searchParams.get('url')
      if (target) {
        try { url = new URL(target, sourceUrl) } catch { continue }
      }
    }
    const targetHost = url.hostname.toLowerCase().replace(/^www\./, '')
    if (!targetHost || ignoredHosts.has(targetHost) || targetHost.endsWith('.google.com') || targetHost.endsWith('.bing.com')) continue
    if (url.pathname === '/search' || url.pathname === '/aclk' || url.pathname === '/url') continue
    if (seen.has(targetHost)) continue
    const companyName = (anchor.innerText || anchor.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160) || host
    if (companyName.length < 2) continue
    const excerpt = (anchor.closest('div')?.innerText || anchor.parentElement?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 600)
    seen.add(targetHost)
    records.push({
      company_name: companyName,
      website: `${url.protocol}//${url.hostname}${url.pathname}`,
      source_url: sourceUrl,
      source_excerpt: excerpt
    })
  }
  return records
}

async function importCurrentPage() {
  if (!isSearchPage()) return
  const taskResponse = await fetch(`${API_BASE}/api/tasks`)
  if (!taskResponse.ok) return
  const taskPayload = await taskResponse.json()
  const task = taskPayload.items?.[0]
  if (!task?.id || !matchesTask(task)) return
  const pageKey = `${task.id}:${window.location.href}`
  const stored = await chrome.storage.local.get('importedPages')
  if (stored.importedPages?.includes(pageKey)) return
  const records = extractVisibleResults()
  if (!records.length) return
  const response = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(task.id)}/discover/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_mode: 'browser', records, weights: {}, signals_by_domain: {} })
  })
  if (!response.ok) return
  const importedPages = [...(stored.importedPages || []).slice(-19), pageKey]
  await chrome.storage.local.set({ importedPages })
}

// Wait briefly for Google/Bing result blocks to finish rendering. This is a
// single bounded attempt per page, not a polling loop or an auto-refresher.
setTimeout(() => { importCurrentPage().catch(() => {}) }, 1200)
