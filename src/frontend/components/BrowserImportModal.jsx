import { useState } from 'react'

export default function BrowserImportModal({ onClose, onImport, loading }) {
  const [raw, setRaw] = useState('')
  const [error, setError] = useState('')

  const submit = (event) => {
    event.preventDefault()
    try {
      const parsed = JSON.parse(raw)
      const sourceRecords = Array.isArray(parsed) ? parsed : parsed.records
      if (!Array.isArray(sourceRecords) || !sourceRecords.length) throw new Error('请输入至少一条结果')
      const records = sourceRecords.map((item, index) => {
        const website = String(item.website || item.url || '').trim()
        if (!website) throw new Error(`第 ${index + 1} 条缺少 website`)
        const companyName = String(item.company_name || item.title || '').trim()
        if (!companyName) throw new Error(`第 ${index + 1} 条缺少 company_name 或 title`)
        const sourceUrl = String(item.source_url || '').trim()
        if (!sourceUrl) throw new Error(`第 ${index + 1} 条缺少 source_url（Google/Bing 结果页）`)
        return {
          company_name: companyName,
          website,
          country: String(item.country || '').trim(),
          source_url: sourceUrl,
          source_excerpt: String(item.source_excerpt || item.excerpt || '').trim(),
        }
      })
      setError('')
      onImport(records)
    } catch (submitError) {
      setError(submitError.message || 'JSON 格式不正确')
    }
  }

  return <div className="modal-backdrop" onClick={onClose}><form className="task-modal browser-import-modal" onSubmit={submit} onClick={(event) => event.stopPropagation()}>
    <button type="button" className="modal-close" onClick={onClose}>×</button>
    <span className="modal-icon">⌁</span><h2>导入浏览器搜索结果</h2>
    <p>当 Google 返回 JavaScript/Consent 页面时，把可见结果整理为 JSON 导入。导入后仍会经过官网抓取、邮箱清洗、评分和来源保存。</p>
    <label>结构化结果 JSON<textarea value={raw} onChange={(event) => setRaw(event.target.value)} placeholder={'[{"title":"公司名称","website":"https://example.com","excerpt":"Google 可见摘要","source_url":"https://www.google.com/search?q=..."}]'} rows={9} required /></label>
    {error && <div className="form-error">{error}</div>}
    <div className="browser-import-boundary">只接受公开可见结果；不会从域名猜邮箱，也不会发送邮件。</div>
    <button type="submit" className="primary-button full" disabled={loading}>{loading ? '导入并核验中…' : '导入并开始核验'} </button>
  </form></div>
}
