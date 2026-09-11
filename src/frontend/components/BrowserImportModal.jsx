import { useState } from 'react'

export default function BrowserImportModal({ onClose, onImport, loading }) {
  const [raw, setRaw] = useState('')
  const [error, setError] = useState('')
  const [summary, setSummary] = useState('')

  const submit = (event) => {
    event.preventDefault()
    try {
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
    <span className="modal-icon">⌁</span><h2>维护工具：导入搜索结果</h2>
    <p>这是搜索源受限时的技术备用入口，正常使用无需操作。导入后仍会经过官网抓取、邮箱清洗、评分和来源保存。</p>
    <label>结构化结果 JSON<textarea value={raw} onChange={(event) => setRaw(event.target.value)} placeholder={'[{"title":"公司名称","website":"https://example.com","excerpt":"Google 可见摘要","source_url":"https://www.google.com/search?q=..."}]'} rows={9} required /></label>
    {error && <div className="form-error">{error}</div>}
    {summary && <div className="browser-import-summary">{summary}</div>}
    <div className="browser-import-boundary">只接受公开可见结果；不会从域名猜邮箱，也不会发送邮件。</div>
    <button type="submit" className="primary-button full" disabled={loading}>{loading ? '导入并核验中…' : '导入并开始核验'} </button>
  </form></div>
}
