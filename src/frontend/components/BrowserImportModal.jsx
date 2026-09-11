import { useState } from 'react'

export default function BrowserImportModal({ onClose, onImport, loading, searchUrl, defaultCountry = '' }) {
  const [raw, setRaw] = useState('')
  const [error, setError] = useState('')
  const [summary, setSummary] = useState('')
  const [mode, setMode] = useState('simple')

  const submit = (event) => {
    event.preventDefault()
    try {
      if (mode === 'simple') {
        const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
        if (!lines.length) throw new Error('请至少填写一家公司的官网')
        const records = lines.map((line, index) => {
          const parts = line.split('|').map((part) => part.trim())
          const website = parts.length === 1 ? parts[0] : parts[parts.length - 1]
          const websiteUrl = new URL(website)
          if (!['http:', 'https:'].includes(websiteUrl.protocol) || !websiteUrl.hostname) throw new Error(`第 ${index + 1} 行官网地址不正确`)
          const companyName = parts.length === 1 ? websiteUrl.hostname.replace(/^www\./, '') : parts[0]
          const country = parts.length >= 3 ? parts[1] : defaultCountry
          if (!companyName) throw new Error(`第 ${index + 1} 行缺少公司名称`)
          return { company_name: companyName, website, country, source_url: searchUrl, source_excerpt: `来自浏览器搜索结果：${companyName}，官网资料将由系统继续核验。` }
        })
        const uniqueRecords = [...new Map(records.map((record) => [new URL(record.website).hostname.toLowerCase().replace(/^www\./, ''), record])).values()]
        setSummary(`已读取 ${records.length} 家，去重后 ${uniqueRecords.length} 家`)
        setError('')
        onImport(uniqueRecords)
        return
      }
      const parsed = JSON.parse(raw)
      const sourceRecords = Array.isArray(parsed) ? parsed : parsed.records
      if (!Array.isArray(sourceRecords) || !sourceRecords.length) throw new Error('请输入至少一条结果')
      const records = sourceRecords.map((item, index) => {
        const website = String(item.website || item.url || '').trim()
        if (!website) throw new Error(`第 ${index + 1} 条缺少 website`)
        const websiteUrl = new URL(website)
        if (!['http:', 'https:'].includes(websiteUrl.protocol) || !websiteUrl.hostname) throw new Error(`第 ${index + 1} 条 website 必须是 HTTP(S) 官网`)
        const companyName = String(item.company_name || item.title || '').trim()
        if (!companyName) throw new Error(`第 ${index + 1} 条缺少 company_name 或 title`)
        const sourceUrl = String(item.source_url || '').trim()
        if (!sourceUrl) throw new Error(`第 ${index + 1} 条缺少 source_url（Google/Bing 结果页）`)
        const sourceHost = new URL(sourceUrl).hostname.toLowerCase().replace(/^www\./, '')
        if (!(sourceHost === 'google.com.hk' || sourceHost.endsWith('google.com') || sourceHost.endsWith('bing.com'))) throw new Error(`第 ${index + 1} 条 source_url 必须来自 Google 或 Bing`)
        return {
          company_name: companyName,
          website,
          country: String(item.country || '').trim(),
          source_url: sourceUrl,
          source_excerpt: String(item.source_excerpt || item.excerpt || '').trim(),
        }
      })
      const uniqueRecords = [...new Map(records.map((record) => {
        const host = new URL(record.website).hostname.toLowerCase().replace(/^www\./, '')
        return [host, record]
      })).values()]
      setSummary(`已读取 ${records.length} 条，按官网域名去重后 ${uniqueRecords.length} 条${records.length === uniqueRecords.length ? '' : `，忽略 ${records.length - uniqueRecords.length} 条重复结果`}`)
      setError('')
      onImport(uniqueRecords)
    } catch (submitError) {
      setSummary('')
      setError(submitError.message || 'JSON 格式不正确')
    }
  }

  return <div className="modal-backdrop" onClick={onClose}><form className="task-modal browser-import-modal" onSubmit={submit} onClick={(event) => event.stopPropagation()}>
    <button type="button" className="modal-close" onClick={onClose}>×</button>
    <span className="modal-icon">⌁</span><h2>用浏览器补充搜索</h2>
    <p>当自动搜索暂时受限时，可以用你的浏览器搜索。导入后系统仍会自动抓官网、提取邮箱并核验国家和业务。</p>
    {mode === 'simple' ? <>
      <a className="outline-button browser-search-link" href={searchUrl} target="_blank" rel="noreferrer">打开当前搜索条件</a>
      <div className="browser-import-format">每行填写：公司名称 | 国家 | 官网地址<br/>例如：Atiplast | France | https://www.atiplast.fr/</div>
      <label>浏览器中找到的官网<textarea value={raw} onChange={(event) => setRaw(event.target.value)} placeholder={'Atiplast | France | https://www.atiplast.fr/\nCME Plast | France | https://www.cmeplast.com/'} rows={7} required /></label>
    </> : <>
      <div className="browser-import-format">高级格式要求：每条结果必须包含 website、company_name、country、source_url。</div>
      <label>高级 JSON 结果<textarea value={raw} onChange={(event) => setRaw(event.target.value)} placeholder={'[{"company_name":"Atiplast","website":"https://www.atiplast.fr/","country":"France","source_url":"https://www.google.com/search?q=..."}]'} rows={9} required /></label>
    </>}
    {error && <div className="form-error">{error}</div>}
    {summary && <div className="browser-import-summary">{summary}</div>}
    <div className="browser-import-boundary">只接受公开可见官网；系统不会从域名猜邮箱，也不会自动发送邮件。</div>
    <details className="maintenance-inline browser-json-fallback"><summary>高级 JSON 导入（维护用）</summary><button type="button" className="text-button" onClick={() => setMode(mode === 'simple' ? 'json' : 'simple')}>{mode === 'simple' ? '切换到 JSON 格式' : '返回简易填写'}</button></details>
    <button type="submit" className="primary-button full" disabled={loading}>{loading ? '导入并核验中…' : '导入并开始核验'} </button>
  </form></div>
}
