const API_BASE = 'http://127.0.0.1:8002'

const button = document.getElementById('import')
const status = document.getElementById('status')

function showStatus(message, error = false) {
  status.textContent = message
  status.className = error ? 'error' : ''
}

function isSearchPage(url) {
  try {
    const parsed = new URL(url)
    return /(^|\.)google\.[^/]+$/.test(parsed.hostname) && parsed.pathname === '/search'
      || parsed.hostname === 'www.bing.com' && parsed.pathname === '/search'
  } catch {
    return false
  }
}

function extractVisibleResults() {
  const pageUrl = window.location.href
  const searchHost = window.location.hostname.toLowerCase()
  const ignoredHosts = new Set([
    searchHost, 'google.com', 'google.com.hk', 'bing.com', 'www.bing.com',
    'youtube.com', 'www.youtube.com', 'facebook.com', 'www.facebook.com',
    'linkedin.com', 'www.linkedin.com', 'wikipedia.org', 'www.wikipedia.org',
    'yelp.com', 'yellowpages.com', 'europages.com', 'inven.com', 'techpilot.com'
  ])
  const seen = new Set()
  const records = []
  for (const anchor of document.querySelectorAll('a[href]')) {
    if (records.length >= 50) break
    let parsed
    try { parsed = new URL(anchor.href, pageUrl) } catch { continue }
    if (!['http:', 'https:'].includes(parsed.protocol)) continue
    const host = parsed.hostname.toLowerCase().replace(/^www\./, '')
    if (!host || ignoredHosts.has(host) || host.endsWith('.google.com') || host.endsWith('.bing.com')) continue
    if (parsed.pathname === '/search' || parsed.href.includes('/aclk?') || parsed.href.includes('/url?')) continue
    if (seen.has(host)) continue
    const companyName = (anchor.innerText || anchor.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160) || host
    if (!companyName || companyName.length < 2) continue
    const parentText = (anchor.closest('div')?.innerText || anchor.parentElement?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 600)
    seen.add(host)
    records.push({
      company_name: companyName,
      website: `${parsed.protocol}//${parsed.hostname}${parsed.pathname}`,
      source_url: pageUrl,
      source_excerpt: parentText
    })
  }
  return records
}

async function getCurrentTask() {
  const response = await fetch(`${API_BASE}/api/tasks`)
  if (!response.ok) throw new Error('本地程序暂时无法读取当前任务')
  const payload = await response.json()
  const task = payload.items?.[0]
  if (!task?.id) throw new Error('请先打开本地客户工作台并设置搜索条件')
  return task
}

button.addEventListener('click', async () => {
  button.disabled = true
  showStatus('正在读取当前搜索页…')
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
    if (!tab?.id || !isSearchPage(tab.url || '')) throw new Error('请先打开 Google 或 Bing 的搜索结果页')
    const [{ result: records }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractVisibleResults })
    if (!records?.length) throw new Error('当前页面没有找到可导入的官网')
    const task = await getCurrentTask()
    showStatus(`已找到 ${records.length} 家，正在核验官网和邮箱…`)
    const response = await fetch(`${API_BASE}/api/tasks/${encodeURIComponent(task.id)}/discover/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_mode: 'browser', records, weights: {}, signals_by_domain: {} })
    })
    const payload = await response.json()
    if (!response.ok) throw new Error(payload.error || '导入失败')
    const summary = payload.summary || {}
    showStatus(`已导入 ${summary.imported_unique_domain_count ?? records.length} 家，系统正在整理结果。`)
  } catch (error) {
    showStatus(error.message || '导入失败，请稍后再试', true)
  } finally {
    button.disabled = false
  }
})
