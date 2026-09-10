import { useEffect, useMemo, useState } from 'react'
import RuleEditorModal from './components/RuleEditorModal'
import BrowserImportModal from './components/BrowserImportModal'

const navItems = [
  ['users', '客户池'],
  ['database', '本地数据库'],
]

const accountNavItems = [
  ['users', '发件人资料'],
  ['settings', '设置'],
]

function Icon({ name, size = 18 }) {
  const paths = {
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
    clipboard: <><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 3V1h8v2M8 8h8M8 12h5M8 16h6"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></>,
    settings: <><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-1.7 1.7-.06-.06a1.7 1.7 0 0 0-1.88-.34 1.7 1.7 0 0 0-1.04 1.56V20h-2.4v-.2a1.7 1.7 0 0 0-1.04-1.56 1.7 1.7 0 0 0-1.88.34l-.06.06-1.7-1.7.06-.06A1.7 1.7 0 0 0 8.4 15a1.7 1.7 0 0 0-1.56-1.04H6v-2.4h.2A1.7 1.7 0 0 0 7.76 10a1.7 1.7 0 0 0-.34-1.88l-.06-.06 1.7-1.7.06.06A1.7 1.7 0 0 0 11 6.76 1.7 1.7 0 0 0 12.04 5.2V5h2.4v.2A1.7 1.7 0 0 0 15.48 6.76a1.7 1.7 0 0 0 1.88-.34l.06-.06 1.7 1.7-.06.06A1.7 1.7 0 0 0 18.72 10a1.7 1.7 0 0 0 1.56 1.04h.2v2.4h-.2A1.7 1.7 0 0 0 19.4 15Z"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    arrow: <><path d="m9 18 6-6-6-6"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    external: <><path d="M14 3h7v7M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></>,
    filter: <path d="M4 6h16M7 12h10m-7 6h4"/>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7"/></>,
  }
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function Status({ status }) {
  const labels = { evidence: ['证据充分', 'green'], complete: ['待补充', 'amber'], researching: ['研究中', 'blue'], review: ['待审核', 'orange'] }
  const [label, tone] = labels[status] || ['待整理', 'amber']
  return <span className={`status status-${tone}`}><i />{label}</span>
}

function splitSearchValues(value) {
  return [...new Set(String(value || '').replace(/[，、；;|]/g, ',').split(',').map((item) => item.trim()).filter(Boolean))]
}

function countryMatchesTarget(country, targets) {
  const value = String(country || '').trim().toLowerCase()
  if (!targets.length) return true
  const aliases = { 德国: 'germany', 英国: 'united kingdom', 美国: 'united states', 加拿大: 'canada', 澳大利亚: 'australia', 法国: 'france', 意大利: 'italy' }
  return targets.some((target) => {
    const normalized = String(target).trim().toLowerCase()
    return value === normalized || value === aliases[normalized]
  })
}

function searchCriteriaWarnings({ product, keywords, countries, industries }) {
  const warnings = []
  const productValue = String(product || '').trim()
  const keywordValues = splitSearchValues(keywords)
  const countryValues = splitSearchValues(countries)
  const industryValues = splitSearchValues(industries)
  if (!productValue && !keywordValues.length) warnings.push('至少填写产品或关键词，系统才能找到相关客户。')
  if (productValue && productValue.length <= 1 && keywordValues.length === 0) warnings.push('产品范围可能过大，建议补充更具体的产品名称或用途。')
  if (countryValues.some((item) => ['全球', '全世界', '不限'].includes(item))) warnings.push('目标市场范围较大，搜索结果可能较分散。')
  if (industryValues.some((item) => ['行业', '公司', '客户', '产品'].includes(item))) warnings.push('行业填写较宽泛，建议补充具体行业或应用场景。')
  return warnings
}

function App() {
  const [selected, setSelected] = useState(null)
  const [remoteLeads, setRemoteLeads] = useState([])
  const [remoteTasks, setRemoteTasks] = useState([])
  const [remoteTaskId, setRemoteTaskId] = useState('')
  const [remoteTaskConfig, setRemoteTaskConfig] = useState(null)
  const [researchRuns, setResearchRuns] = useState([])
  const [researchLoading, setResearchLoading] = useState(false)
  const [discoverLoading, setDiscoverLoading] = useState(false)
  const [contactRefreshLoading, setContactRefreshLoading] = useState(false)
  const [discoverySummary, setDiscoverySummary] = useState(null)
  const [discoveryError, setDiscoveryError] = useState(null)
  const [mailboxStatus, setMailboxStatus] = useState(null)
  const [mailThreads, setMailThreads] = useState([])
  const [replyAnalyses, setReplyAnalyses] = useState([])
  const [followUpTasks, setFollowUpTasks] = useState([])
  const [replyLoading, setReplyLoading] = useState(false)
  const [selectedResearch, setSelectedResearch] = useState(null)
  const [selectedDraft, setSelectedDraft] = useState(null)
  const [batchDrafts, setBatchDrafts] = useState([])
  const [batchIndex, setBatchIndex] = useState(0)
  const [batchSelectedIds, setBatchSelectedIds] = useState([])
  const [batchTranslations, setBatchTranslations] = useState({})
  const [batchTranslationLoading, setBatchTranslationLoading] = useState(false)
  const [batchPreview, setBatchPreview] = useState(null)
  const [batchLoading, setBatchLoading] = useState(false)
  const [selectedSendHistory, setSelectedSendHistory] = useState([])
  const [selectedLeadAudit, setSelectedLeadAudit] = useState([])
  const [leadTransitionLoading, setLeadTransitionLoading] = useState(false)
  const [translatedDraft, setTranslatedDraft] = useState(null)
  const [translationLoading, setTranslationLoading] = useState(false)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [safetyLoading, setSafetyLoading] = useState(false)
  const [sendSafety, setSendSafety] = useState(null)
  const [sendLoading, setSendLoading] = useState(false)
  const [apiState, setApiState] = useState('loading')
  const [query, setQuery] = useState('')
  const [leadView, setLeadView] = useState('qualified')
  const [activeNav, setActiveNav] = useState('客户池')
  const [detailTab, setDetailTab] = useState('概览')
  const [language, setLanguage] = useState('中文')
  const [draftStatus, setDraftStatus] = useState('pending')
  const [showTask, setShowTask] = useState(false)
  const [showRuleEditor, setShowRuleEditor] = useState(false)
  const [showBrowserImport, setShowBrowserImport] = useState(false)
  const [showMaintenanceTools, setShowMaintenanceTools] = useState(false)
  const [browserImportLoading, setBrowserImportLoading] = useState(false)
  const [discoveryRun, setDiscoveryRun] = useState(null)
  const [toast, setToast] = useState('')
  const [searchProduct, setSearchProduct] = useState('')
  const [searchKeywords, setSearchKeywords] = useState('')
  const [searchCountries, setSearchCountries] = useState('')
  const [searchIndustries, setSearchIndustries] = useState('')
  const [databaseOverview, setDatabaseOverview] = useState(null)
  const [databaseLoading, setDatabaseLoading] = useState(false)
  const [databaseExportLoading, setDatabaseExportLoading] = useState(false)
  const [settingsStatus, setSettingsStatus] = useState(null)
  const searchWarnings = searchCriteriaWarnings({ product: searchProduct, keywords: searchKeywords, countries: searchCountries, industries: searchIndustries })
  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const taskResponse = await fetch('/api/tasks')
        if (!taskResponse.ok) throw new Error('tasks request failed')
        const tasks = await taskResponse.json()
        const availableTasks = tasks.items || []
        setRemoteTasks(availableTasks)
        const task = availableTasks[0]
        if (!task) {
          if (!cancelled) { setRemoteLeads([]); setSelected(null); setApiState('empty') }
          return
        }
        if (!cancelled) { setRemoteTaskId(task.id); setRemoteTaskConfig(task) }
      } catch {
        if (!cancelled) { setRemoteTasks([]); setRemoteLeads([]); setSelected(null); setApiState('error') }
      }
    }
    load()
    return () => { cancelled = true }
  }, [])
  useEffect(() => {
    const criteria = remoteTaskConfig?.criteria
    if (!criteria) return
    setSearchProduct(criteria.product || '')
    setSearchKeywords((criteria.keywords || []).join(', '))
    setSearchCountries((criteria.countries || []).join(', '))
    setSearchIndustries((criteria.industries || []).join(', '))
  }, [remoteTaskConfig?.id])
  useEffect(() => {
    if (activeNav !== '本地数据库') return undefined
    let cancelled = false
    setDatabaseLoading(true)
    const suffix = remoteTaskId ? `?task_id=${encodeURIComponent(remoteTaskId)}` : ''
    fetch(`/api/database/overview${suffix}`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('database overview failed')))
      .then((data) => { if (!cancelled) setDatabaseOverview(data) })
      .catch(() => { if (!cancelled) setDatabaseOverview(null) })
      .finally(() => { if (!cancelled) setDatabaseLoading(false) })
    return () => { cancelled = true }
  }, [activeNav, remoteLeads, remoteTaskId])
  useEffect(() => {
    if (activeNav !== '设置') return undefined
    let cancelled = false
    fetch('/api/settings/status')
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('settings status failed')))
      .then((data) => { if (!cancelled) setSettingsStatus(data) })
      .catch(() => { if (!cancelled) setSettingsStatus(null) })
    return () => { cancelled = true }
  }, [activeNav])
  useEffect(() => {
    if (!remoteTaskId) return undefined
    let cancelled = false
    const loadDrafts = () => fetch(`/api/tasks/${remoteTaskId}/drafts`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('draft list failed')))
      .then((data) => {
        if (!cancelled) {
          const drafts = data.items || []
          setBatchDrafts(drafts)
          setBatchSelectedIds((ids) => ids.filter((id) => drafts.some((draft) => draft.id === id)))
        }
      })
      .catch(() => { if (!cancelled) setBatchDrafts([]) })
    loadDrafts()
    const timer = window.setInterval(loadDrafts, 1800)
    return () => { cancelled = true; window.clearInterval(timer) }
  }, [remoteTaskId, selectedDraft?.id, selectedDraft?.status])
  useEffect(() => {
    if (!remoteTaskId) return undefined
    let cancelled = false
    const loadLeads = async () => {
      try {
        const leadResponse = await fetch(`/api/tasks/${remoteTaskId}/leads`)
        if (!leadResponse.ok) throw new Error('leads request failed')
        const data = await leadResponse.json()
        const loaded = (data.items || []).map(mapRemoteLead)
        if (!cancelled) {
          setRemoteLeads(loaded)
          setDiscoverySummary(data.summary || null)
          setSelected(loaded.find((lead) => lead.qualified) || null)
          setApiState(loaded.length ? 'connected' : 'empty')
        }
      } catch {
        if (!cancelled) { setRemoteLeads([]); setSelected(null); setApiState('error') }
      }
    }
    loadLeads()
    return () => { cancelled = true }
  }, [remoteTaskId])
  useEffect(() => {
    if (!remoteTaskId) return undefined
    let cancelled = false
    let timer
    const loadDiscoveryRuns = async () => {
      try {
        const response = await fetch(`/api/tasks/${remoteTaskId}/discovery-runs`)
        if (!response.ok) throw new Error('discovery runs request failed')
        const data = await response.json()
        const latest = (data.items || []).at(-1) || null
        if (cancelled) return
        setDiscoveryRun(latest)
        if (latest?.status === 'running') timer = window.setTimeout(loadDiscoveryRuns, 1000)
        if (latest?.status === 'failed') {
          setDiscoveryError('本次暂未找到新的合格客户，可以稍后再试。')
        }
        if (latest?.status === 'succeeded') {
          setDiscoveryError(null)
          const leadResponse = await fetch(`/api/tasks/${remoteTaskId}/leads`)
          if (!leadResponse.ok) return
          const leads = await leadResponse.json()
          setRemoteLeads((leads.items || []).map(mapRemoteLead))
          setDiscoverySummary(leads.summary || null)
          setApiState((leads.items || []).length ? 'connected' : 'empty')
        }
      } catch { if (!cancelled) setDiscoveryRun(null) }
    }
    loadDiscoveryRuns()
    return () => { cancelled = true; if (timer) window.clearTimeout(timer) }
  }, [remoteTaskId, discoveryRun?.id, discoveryRun?.status])
  useEffect(() => {
    if (!remoteTaskId) return undefined
    let cancelled = false
    Promise.allSettled([
      fetch('/api/mailbox/status').then((response) => response.ok ? response.json() : Promise.reject(new Error('mailbox status failed'))),
      fetch(`/api/tasks/${remoteTaskId}/mail-threads`).then((response) => response.ok ? response.json() : Promise.reject(new Error('mail threads failed'))),
      fetch(`/api/tasks/${remoteTaskId}/reply-analyses`).then((response) => response.ok ? response.json() : Promise.reject(new Error('reply analyses failed'))),
      fetch(`/api/tasks/${remoteTaskId}/follow-up-tasks`).then((response) => response.ok ? response.json() : Promise.reject(new Error('follow-up tasks failed'))),
    ]).then(([statusResult, threadsResult, analysesResult, followUpResult]) => {
      if (cancelled) return
      if (statusResult.status === 'fulfilled') setMailboxStatus(statusResult.value)
      if (threadsResult.status === 'fulfilled') setMailThreads(threadsResult.value.items || [])
      if (analysesResult.status === 'fulfilled') setReplyAnalyses(analysesResult.value.items || [])
      if (followUpResult.status === 'fulfilled') setFollowUpTasks(followUpResult.value.items || [])
    })
    return () => { cancelled = true }
  }, [remoteTaskId])
  useEffect(() => {
    if (!remoteTaskId) return undefined
    let cancelled = false
    let timer
    const loadRuns = async () => {
      try {
        const response = await fetch(`/api/tasks/${remoteTaskId}/research-runs`)
        if (!response.ok) throw new Error('research runs request failed')
        const data = await response.json()
        if (!cancelled) {
          const runs = data.items || []
          setResearchRuns(runs)
          if (runs.some((run) => run.status === 'running')) {
            timer = window.setTimeout(loadRuns, 1200)
          } else if (runs.some((run) => ['succeeded', 'review_required'].includes(run.status))) {
            const leadResponse = await fetch(`/api/tasks/${remoteTaskId}/leads`)
            if (!leadResponse.ok) throw new Error('leads refresh request failed')
            const leads = await leadResponse.json()
            const loaded = (leads.items || []).map(mapRemoteLead)
            if (!cancelled) {
              setRemoteLeads(loaded)
              setDiscoverySummary(leads.summary || null)
              setSelected((current) => current ? loaded.find((lead) => lead.domain === current.domain) || current : loaded.find((lead) => lead.qualified) || null)
            }
          }
        }
      } catch {
        if (!cancelled) setResearchRuns([])
      }
    }
    loadRuns()
    return () => { cancelled = true; if (timer) window.clearTimeout(timer) }
  }, [remoteTaskId])
  useEffect(() => {
    if (!remoteTaskId || !selected?.domain) return undefined
    let cancelled = false
    setSelectedResearch(null)
    setSelectedDraft(null)
    setSelectedSendHistory([])
    setSelectedLeadAudit([])
    setSelectedLeadAudit([])
    Promise.all([
      fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}`),
      fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/audit-events`),
    ])
      .then(async ([detailResponse, auditResponse]) => {
        if (!detailResponse.ok || !auditResponse.ok) throw new Error('lead detail failed')
        return Promise.all([detailResponse.json(), auditResponse.json()])
      })
      .then(([data, audit]) => { if (!cancelled) { setSelectedResearch(data.research || null); setSelectedDraft(data.draft || null); setSelectedSendHistory(data.send_history || []); setSelectedLeadAudit(audit.items || []); setTranslatedDraft(null) } })
      .catch(() => { if (!cancelled) { setSelectedResearch(null); setSelectedLeadAudit([]) } })
    return () => { cancelled = true }
  }, [remoteTaskId, selected?.domain])
  useEffect(() => {
    const run = researchRuns.find((item) => item.domain === selected?.domain)
    if (!remoteTaskId || !selected?.domain || !run || !['succeeded', 'review_required'].includes(run.status)) return undefined
    let cancelled = false
    fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}`)
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('research detail failed')))
      .then((data) => { if (!cancelled) { setSelectedResearch(data.research || null); setSelectedDraft(data.draft || null) } })
      .catch(() => {})
    return () => { cancelled = true }
  }, [researchRuns, remoteTaskId, selected?.domain])
  // 候选池仍完整保留在本地数据库；工作台只展示达到交付门槛的客户。
  const targetCountries = splitSearchValues(searchCountries)
  const targetLeads = remoteLeads.filter((lead) => countryMatchesTarget(lead.country, targetCountries))
  const qualifiedLeads = targetLeads.filter((lead) => lead.qualified && !lead.contacted)
  const displayLeads = leadView === 'qualified' ? qualifiedLeads : targetLeads
  const filteredLeads = useMemo(() => displayLeads.filter((lead) => `${lead.name} ${lead.country} ${lead.type}`.toLowerCase().includes(query.toLowerCase())), [displayLeads, query])
  const activeLead = selected ? { ...selected, type: selectedResearch ? customerTypeLabel(selectedResearch.customer_type) : selected.type, detail: selectedResearch?.business_summary || selected.detail, research: selectedResearch, draft: selectedDraft, sendHistory: selectedSendHistory, auditEvents: selectedLeadAudit, researchRun: researchRuns.find((run) => run.domain === selected.domain), isRemote: true } : null

  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600) }
  const exportDatabase = async () => {
    setDatabaseExportLoading(true)
    try {
      const suffix = remoteTaskId ? `?task_id=${encodeURIComponent(remoteTaskId)}` : ''
      const response = await fetch(`/api/database/export${suffix}`)
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || '导出失败')
      const bytes = Uint8Array.from(atob(payload.content_base64), (character) => character.charCodeAt(0))
      const blob = new Blob([bytes], { type: payload.content_type })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = payload.filename || '客户资料库.xlsx'
      link.click()
      URL.revokeObjectURL(url)
      notify(`已导出 ${payload.row_count || 0} 条客户资料`)
    } catch (error) { notify(error.message || '导出失败，请稍后重试') } finally { setDatabaseExportLoading(false) }
  }
  const selectLead = (lead) => { setSelected(lead); setDetailTab('概览'); setDraftStatus('pending'); setTranslatedDraft(null) }
  const selectDatabaseLead = (item) => {
    const task = remoteTasks.find((candidate) => candidate.id === item.task_id)
    if (task) {
      setRemoteTaskId(task.id)
      setRemoteTaskConfig(task)
    }
    // The database also contains retained candidates that are not yet
    // qualified. Switch the pool to the full retained set so their detail
    // panel remains reachable after a database click.
    setLeadView('all')
    setActiveNav('客户池')
    selectLead(mapRemoteLead(item))
  }
  const selectTask = (event) => {
    const task = remoteTasks.find((item) => item.id === event.target.value)
    if (!task) return
    setRemoteTaskId(task.id)
    setRemoteTaskConfig(task)
    setRemoteLeads([])
    setDiscoverySummary(null)
    setDiscoveryRun(null)
    setResearchRuns([])
    setMailThreads([])
    setReplyAnalyses([])
    setFollowUpTasks([])
    setApiState('loading')
    setSelected(null)
    setSelectedResearch(null)
    setSelectedDraft(null)
    setSelectedSendHistory([])
    setTranslatedDraft(null)
    setDetailTab('概览')
  }
  const translateDraft = async () => {
    if (!selectedDraft?.id) return
    setTranslationLoading(true)
    try {
      const response = await fetch(`/api/drafts/${selectedDraft.id}/translate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ target_language: 'zh-CN' }) })
      if (!response.ok) throw new Error('translation failed')
      const payload = await response.json()
      if (!payload?.body || /Error 500|Server Error|That’s an error/i.test(payload.body)) throw new Error('translation failed')
      setTranslatedDraft(payload)
      setLanguage('中文')
      notify('中文预览已生成，英文邮件内容未改变')
    } catch { notify('翻译失败，请检查本地翻译服务或网络') } finally { setTranslationLoading(false) }
  }
  const reviewDraft = async (action, note) => {
    if (!selectedDraft?.id) return
    if ((action === 'request-revision' || action === 'reject') && !note.trim()) { notify('请填写处理意见'); return }
    setReviewLoading(true)
    try {
      const response = await fetch(`/api/drafts/${selectedDraft.id}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note: note.trim() }) })
      if (!response.ok) throw new Error('review failed')
      setSelectedDraft(await response.json())
      setSendSafety(null)
      notify(action === 'approve' ? '草稿已批准，等待发送' : action === 'request-revision' ? '草稿已退回修改' : '草稿已拒绝')
    } catch { notify('审核操作失败，请稍后重试') } finally { setReviewLoading(false) }
  }
  const reviewResearchField = async (fieldKey, value) => {
    if (!remoteTaskId || !selected?.domain) return
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/research-fields/${fieldKey}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'verified', value }) })
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'research field review failed')
      setSelectedResearch(data)
      notify('字段已人工确认，来源证据已保留')
    } catch (error) { notify(error.message || '字段确认失败') }
  }
  const generateDraft = async (template, product) => {
    if (!remoteTaskId || !selected?.domain) return
    setReviewLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/draft`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ template, product }) })
      if (!response.ok) throw new Error('draft generation failed')
      setSelectedDraft(await response.json())
      setSendSafety(null)
      setTranslatedDraft(null)
      notify('邮件草稿已生成，请人工审核')
    } catch { notify('邮件生成失败，请确认客户资料已整理完成') } finally { setReviewLoading(false) }
  }
  const reviewBatchDraft = async (draftId, action = 'approve') => {
    setBatchLoading(true)
    try {
      const response = await fetch(`/api/drafts/${draftId}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ note: '' }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'batch review failed')
      setBatchDrafts((items) => items.map((draft) => draft.id === draftId ? payload : draft))
      notify(action === 'approve' ? '邮件已批准' : '邮件已退回修改')
    } catch (error) { notify(error.message || '批量审核失败') } finally { setBatchLoading(false) }
  }
  const translateBatchDraft = async (draftId) => {
    if (!draftId || batchTranslationLoading) return
    if (batchTranslations[draftId]) return
    setBatchTranslationLoading(true)
    try {
      const response = await fetch(`/api/drafts/${draftId}/translate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ target_language: 'zh-CN' }) })
      const payload = await response.json()
      if (!response.ok || !payload?.body || /Error 500|Server Error|That’s an error/i.test(payload.body)) throw new Error('translation failed')
      setBatchTranslations((items) => ({ ...items, [draftId]: payload }))
      notify('中文预览已生成，英文邮件内容未改变')
    } catch { notify('中文预览暂时生成失败，请稍后重试') } finally { setBatchTranslationLoading(false) }
  }
  const sendBatchDrafts = async (confirmed = false) => {
    if (!remoteTaskId || !batchSelectedIds.length) { notify('请先选择要发送的邮件'); return }
    setBatchLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/drafts/batch-send`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ draft_ids: batchSelectedIds, confirmed }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'batch send failed')
      if (!confirmed) { setBatchPreview(payload); return }
      setBatchPreview(null)
      notify(`批量发送完成：${payload.sent_count || 0} 封成功，${payload.failed_count || 0} 封失败`)
      setBatchSelectedIds([])
    } catch (error) { notify(error.message || '批量发送失败') } finally { setBatchLoading(false) }
  }
  const runSendSafetyCheck = async () => {
    if (!selectedDraft?.id) return
    setSafetyLoading(true)
    try {
      const response = await fetch(`/api/drafts/${selectedDraft.id}/send-check`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recent_contact_days: 7 }),
      })
      const payload = await response.json()
      if (!response.ok && response.status !== 503) throw new Error(payload.error || 'send safety check failed')
      setSendSafety(payload)
      notify(payload.allowed ? '发送前检查通过，但仍需人工确认' : '发送前检查已阻断，请处理风险原因')
    } catch (error) { notify(error.message || '发送前检查失败') } finally { setSafetyLoading(false) }
  }
  const refreshAfterSend = async () => {
    if (!remoteTaskId) return
    const [leadResponse, databaseResponse] = await Promise.all([
      fetch(`/api/tasks/${remoteTaskId}/leads`),
      fetch('/api/database/overview'),
    ])
    if (!leadResponse.ok || !databaseResponse.ok) return
    const leadData = await leadResponse.json()
    const loaded = (leadData.items || []).map(mapRemoteLead)
    setRemoteLeads(loaded)
    setDiscoverySummary(leadData.summary || null)
    setSelected((current) => current ? loaded.find((lead) => lead.domain === current.domain) || current : null)
    setDatabaseOverview(await databaseResponse.json())
  }
  const sendDraft = async () => {
    if (!selectedDraft?.id || !sendSafety?.allowed) return
    setSendLoading(true)
    try {
      const response = await fetch(`/api/drafts/${selectedDraft.id}/send`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          confirmed: true,
          recipient_email: selectedDraft.recipient_email,
          subject: selectedDraft.subject,
          body: selectedDraft.body,
          idempotency_key: `manual-${selectedDraft.id}`,
        }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'email send failed')
      notify(`邮件已发送至 ${payload.attempt?.recipient_email || selectedDraft.recipient_email}`)
      setSendSafety(null)
      await refreshAfterSend()
    } catch (error) { notify(error.message || '邮件发送失败') } finally { setSendLoading(false) }
  }
  const updateContact = async (email, sourceUrl, sourceExcerpt) => {
    if (!remoteTaskId || !selected?.domain) return
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/contact`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, source_url: sourceUrl, source_excerpt: sourceExcerpt }) })
      if (!response.ok) throw new Error('contact update failed')
      const item = await response.json()
      const updated = mapRemoteLead(item)
      setRemoteLeads((items) => (items || []).map((lead) => lead.domain === updated.domain ? updated : lead))
      setSelected(updated)
      notify('联系人已按来源证据更新，可继续生成邮件')
    } catch { notify('联系人更新失败，请检查邮箱格式和来源证据') }
  }
  const refreshContacts = async () => {
    if (!remoteTaskId || !selected?.domain) return
    setContactRefreshLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/contacts/discover`, { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'contact refresh failed')
      const refreshed = mapRemoteLead(payload)
      setRemoteLeads((items) => (items || []).map((lead) => lead.domain === refreshed.domain ? refreshed : lead))
      setSelected(refreshed)
      notify(`官网联系人已更新：${refreshed.email?.includes('@') ? '发现公开邮箱' : '当前未发现公开邮箱'}`)
    } catch (error) { notify(error.message || '官网联系人重新核验失败') } finally { setContactRefreshLoading(false) }
  }
  const transitionLead = async (target, actor, note) => {
    if (!remoteTaskId || !selected?.domain) return
    setLeadTransitionLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/transition`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: target, actor, note }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'lead transition failed')
      const updated = mapRemoteLead(payload)
      setRemoteLeads((items) => (items || []).map((lead) => lead.domain === updated.domain ? updated : lead))
      setSelected(updated)
      const auditResponse = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/audit-events`)
      if (auditResponse.ok) setSelectedLeadAudit((await auditResponse.json()).items || [])
      notify('客户状态已更新')
    } catch (error) { notify(error.message || '客户状态更新失败，请检查状态转换和审核人') } finally { setLeadTransitionLoading(false) }
  }
  const startResearch = async (sourceUrl, maxAttempts, idempotencyKey) => {
    if (!remoteTaskId || !selected?.domain) return
    setResearchLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/research`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_url: sourceUrl, max_attempts: maxAttempts, idempotency_key: idempotencyKey }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'research start failed')
      setResearchRuns((items) => [payload.run, ...items.filter((run) => run.id !== payload.run.id)])
      notify(response.status === 202 ? '客户资料正在整理，完成后会自动更新' : '客户资料已更新')
    } catch (error) { notify(error.message || '背调任务启动失败') } finally { setResearchLoading(false) }
  }
  const discoverLeads = async () => {
    if (!remoteTaskId || discoverLoading) return
    setDiscoverLoading(true)
    setDiscoveryError(null)
    try {
      const criteria = {
        ...(remoteTaskConfig?.criteria || {}),
        product: searchProduct.trim(),
        keywords: splitSearchValues(searchKeywords),
        countries: splitSearchValues(searchCountries),
        industries: splitSearchValues(searchIndustries),
        daily_limit: 30,
        qualified_lead_limit: 30,
        require_public_email: true,
      }
      const criteriaResponse = await fetch(`/api/tasks/${remoteTaskId}/criteria`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ criteria }) })
      if (!criteriaResponse.ok) throw new Error('搜索条件保存失败，请稍后重试')
      const savedTask = await criteriaResponse.json()
      setRemoteTaskConfig(savedTask)
      setRemoteTasks((items) => items.map((item) => item.id === savedTask.id ? savedTask : item))
      const response = await fetch(`/api/tasks/${remoteTaskId}/discover`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      const payload = await response.json()
      if (!response.ok) {
        const error = new Error(payload.error || 'lead discovery failed')
        error.code = payload.code
        error.retryable = payload.retryable
        throw error
      }
      if (response.status === 202) {
        setDiscoveryRun(payload.run || null)
        notify('正在整理客户资料，完成后会自动更新')
        return
      }
      const loaded = (payload.items || []).map(mapRemoteLead)
      setRemoteLeads(loaded)
      setSelected(loaded.find((lead) => lead.qualified) || null)
      setApiState(loaded.length ? 'connected' : 'empty')
      const summary = payload.summary
      setDiscoverySummary(summary)
      setDiscoveryRun(null)
      const funnel = summary?.funnel || {}
      notify(`搜索完成：找到 ${summary?.qualified_count || 0} 家可发送客户`)
    } catch (error) {
      setDiscoveryError({ code: error.code || 'discovery_failed', message: error.message, retryable: error.retryable !== false })
      notify(error.code === 'search_provider_unavailable' ? '这次没有找到新的合格客户，已有客户仍可继续使用' : error.message || '这次没有找到新的合格客户')
    } finally { setDiscoverLoading(false) }
  }
  const importBrowserResults = async (records) => {
    if (!remoteTaskId || browserImportLoading) return
    setBrowserImportLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/discover/import`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_mode: 'browser', records, weights: {}, signals_by_domain: {} }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'browser result import failed')
      const loaded = (payload.items || []).map(mapRemoteLead)
      setRemoteLeads(loaded)
      setSelected(loaded.find((lead) => lead.qualified) || null)
      setApiState(loaded.length ? 'connected' : 'empty')
      setShowBrowserImport(false)
      setDiscoveryError(null)
      const summary = payload.summary
      setDiscoverySummary(summary)
      const funnel = summary?.funnel || {}
      notify(`导入完成：找到 ${summary?.qualified_count || 0} 家可发送客户`)
    } catch (error) {
      setDiscoveryError({ code: 'browser_import_failed', message: error.message, retryable: false })
      notify(error.message || '导入失败，请检查结果格式')
    } finally { setBrowserImportLoading(false) }
  }
  const syncMailbox = async () => {
    if (!remoteTaskId) return
    setReplyLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/mailbox/sync`, { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'mailbox sync failed')
      notify(`收件箱同步完成：新增 ${payload.inserted} 封`)
    } catch (error) { notify(error.message || '收件箱同步失败') } finally { setReplyLoading(false) }
  }
  const testMailbox = async () => {
    setReplyLoading(true)
    try {
      const response = await fetch('/api/mailbox/test', { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'mailbox connection failed')
      notify('阿里邮箱只读连接成功，未读取邮件')
    } catch (error) { notify(error.message || '阿里邮箱连接测试失败') } finally { setReplyLoading(false) }
  }
  const analyzeReplies = async () => {
    if (!remoteTaskId || !mailThreads.length) return
    setReplyLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/reply-analyses/run`, { method: 'POST' })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'reply analysis failed')
      setReplyAnalyses(payload.items || [])
      const followUpResponse = await fetch(`/api/tasks/${remoteTaskId}/follow-up-tasks`)
      if (followUpResponse.ok) setFollowUpTasks((await followUpResponse.json()).items || [])
      const skipped = payload.skipped_system_notifications ? `，跳过 ${payload.skipped_system_notifications} 条系统通知` : ''
      notify(`回复分析完成：${payload.analyzed} 条新分析，${payload.reused} 条复用${skipped}`)
    } catch (error) { notify(error.message || '回复分析失败') } finally { setReplyLoading(false) }
  }
  const generateReplyDraft = async (messageId) => {
    if (!remoteTaskId || !messageId) return
    setReplyLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/reply-drafts`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_id: messageId }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'reply draft generation failed')
      const replyLead = remoteLeads.find((lead) => lead.domain === payload.lead_domain)
      if (replyLead) setSelected(replyLead)
      setSelectedDraft(payload)
      setTranslatedDraft(null)
      setDetailTab('邮件草稿')
      notify('跟进邮件草稿已生成，请人工审核，尚未发送')
    } catch (error) { notify(error.message || '跟进草稿生成失败，请确认已完成回复分析') } finally { setReplyLoading(false) }
  }
  const updateFollowUpStatus = async (followUpId, status) => {
    if (!remoteTaskId) return
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/follow-up-tasks/${followUpId}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'follow-up update failed')
      setFollowUpTasks((items) => items.map((item) => item.id === followUpId ? payload.item : item))
      notify('跟进状态已更新')
    } catch (error) { notify(error.message || '跟进状态更新失败') }
  }
  const saveSenderProfile = async (profile) => {
    if (!remoteTaskId) return
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/sender-profile`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile) })
      if (!response.ok) throw new Error('sender profile update failed')
      setRemoteTaskConfig(await response.json())
      await fetch(`/api/tasks/${remoteTaskId}/leads`)
      notify('发件人资料已保存，符合条件的邮件会自动生成')
    } catch { notify('发件人资料保存失败，请稍后重试') }
  }
  const createTask = async (event) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload = {
      name: form.get('name'),
      criteria: {
        product: form.get('product'),
        countries: splitSearchValues(form.get('countries')),
        industries: splitSearchValues(form.get('industries')),
        customer_types: [],
        language: form.get('language') || 'English',
        daily_limit: 30,
        qualified_lead_limit: 30,
        candidate_limit: 100,
        minimum_qualification_score: 40,
        require_public_email: true,
        keywords: splitSearchValues(form.get('keywords')),
        business_offerings: [],
        research_fields: [],
      },
      sender_profile: {
        company_name: form.get('senderCompany'),
        contact_name: form.get('senderName'),
        position: form.get('senderPosition'),
      },
    }
    try {
      const response = await fetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!response.ok) throw new Error('task creation failed')
      const task = await response.json()
      setRemoteTasks((items) => [task, ...items.filter((item) => item.id !== task.id)])
      setRemoteTaskId(task.id)
      setRemoteTaskConfig(task)
      setRemoteLeads([])
      setDiscoverySummary(null)
      setDiscoveryRun(null)
      setSelected(null)
      setApiState('loading')
      setShowTask(false)
      notify('任务草稿已保存，已切换到当前任务')
    } catch {
      notify('任务保存失败，请稍后重试')
    }
  }
  const saveCriteria = async (criteria) => {
    if (!remoteTaskId) return
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/criteria`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ criteria }) })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'criteria update failed')
      setRemoteTasks((items) => items.map((item) => item.id === payload.id ? payload : item))
      setRemoteTaskConfig(payload)
      setShowRuleEditor(false)
      notify('研究规则已保存，后续背调会使用新配置')
    } catch (error) { notify(error.message || '研究规则保存失败，请检查配置') }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">✦</span><span>NORTHSTAR OPS</span></div>
      <nav>{navItems.map(([icon, label]) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => setActiveNav(label)}><Icon name={icon} /><span>{label}</span></button>)}<div className="nav-divider"/><div className="nav-group-label">工作配置</div>{accountNavItems.map(([icon, label]) => <button key={label} className={`nav-item nav-item-sub ${activeNav === label ? 'active' : ''}`} onClick={() => setActiveNav(label)}><Icon name={icon} /><span>{label}</span></button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-rule"/><p>让中国制造<br/>连接全球真实需求</p><small>NORTHSTAR OPS</small></div>
    </aside>
    <main className="main-shell">
      <header className="topbar"><div className="top-actions"><button className="icon-button" onClick={() => notify('暂无新的系统通知')} aria-label="通知"><Icon name="bell" size={20}/><i className="notification-dot"/></button></div></header>
      <div className="content">
      {activeNav === '本地数据库' ? <DatabasePanel overview={databaseOverview} loading={databaseLoading} exportLoading={databaseExportLoading} onExport={exportDatabase} onSelect={selectDatabaseLead} searchCountries={searchCountries}/> : activeNav === '发件人资料' ? <SenderProfilePage taskConfig={remoteTaskConfig} onSave={saveSenderProfile}/> : activeNav === '设置' ? <SettingsPanel status={settingsStatus} mailboxStatus={mailboxStatus}/> : <>
        <div className="page-heading"><div><h1>找客户</h1><p>输入目标条件，优先展示官网有公开邮箱的客户</p></div>{!remoteTaskId && <button className="primary-button" onClick={() => setShowTask(true)}><Icon name="plus" size={19}/>开始使用</button>}</div>
        <div className={`data-notice ${apiState}`}><span />{apiState === 'loading' ? '正在准备客户资料…' : apiState === 'connected' ? '客户资料已准备就绪' : apiState === 'empty' ? '当前还没有客户资料' : '客户资料暂时无法读取'}</div>
        <section className="search-panel panel"><div className="search-panel-heading"><div><h2>搜索条件</h2><p>常用条件放在这里，中文也可以直接输入</p></div><button type="button" className="primary-button" disabled={!remoteTaskId || discoverLoading || discoveryRun?.status === 'running'} onClick={discoverLeads}><Icon name="search" size={16}/>{discoverLoading || discoveryRun?.status === 'running' ? '正在搜索…' : '搜索可发送客户'}</button></div><div className="search-fields"><label>产品或业务<input value={searchProduct} onChange={(event) => setSearchProduct(event.target.value)} placeholder="例如：注塑件、精密零件" /></label><label>关键词<input value={searchKeywords} onChange={(event) => setSearchKeywords(event.target.value)} placeholder="例如：精密零件、注塑件" /></label><label>目标国家 / 地区<input value={searchCountries} onChange={(event) => setSearchCountries(event.target.value)} placeholder="例如：德国、墨西哥" /></label><label>行业<input value={searchIndustries} onChange={(event) => setSearchIndustries(event.target.value)} placeholder="例如：汽车、电子" /></label>{searchWarnings.length > 0 && <div className="criteria-hint">{searchWarnings.map((warning) => <span key={warning}>{warning}</span>)}</div>}{discoveryError && <div className="discovery-friendly-error">{discoveryError}</div>}</div><div className="search-panel-foot"><details className="maintenance-inline"><summary>维护工具（不常用）</summary><div className="maintenance-inline-body"><button type="button" className="outline-button" onClick={() => setShowRuleEditor(true)}>研究规则</button><button type="button" className="outline-button" onClick={() => setShowBrowserImport(true)}>备用导入</button></div></details></div></section>
        {discoverySummary ? <DiscoveryFunnel summary={discoverySummary} visibleCount={filteredLeads.length}/> : null}
        <BatchMailPanel drafts={batchDrafts} index={batchIndex} onIndexChange={setBatchIndex} selectedIds={batchSelectedIds} onToggle={(id) => setBatchSelectedIds((items) => items.includes(id) ? items.filter((item) => item !== id) : items.length >= 30 ? items : [...items, id])} onReview={reviewBatchDraft} translations={batchTranslations} translationLoading={batchTranslationLoading} onTranslate={translateBatchDraft} onPreview={() => sendBatchDrafts(false)} onConfirm={() => sendBatchDrafts(true)} loading={batchLoading} preview={batchPreview}/>
        <ReplyCenter mailboxStatus={mailboxStatus} threads={mailThreads} analyses={replyAnalyses} followUpTasks={followUpTasks} loading={replyLoading} onTest={testMailbox} onSync={syncMailbox} onAnalyze={analyzeReplies} onGenerateDraft={generateReplyDraft} onFollowUpStatus={updateFollowUpStatus}/>
        <section className="workspace-grid">
          <div className="lead-panel panel"><div className="panel-heading"><div><h2>可发送客户 <span>共 {filteredLeads.length} 个</span></h2><p>已找到官网公开邮箱，可以直接联系</p></div></div><div className="table-head"><span className="checkbox"/><span>公司名称</span><span>国家 / 地区</span><span>客户类型</span><span>状态</span><span/></div><div className="lead-list">{filteredLeads.length ? filteredLeads.map((lead) => <button className={`lead-row ${selected?.name === lead.name ? 'selected' : ''}`} key={lead.name} onClick={() => selectLead(lead)}><span className={`checkbox ${selected?.name === lead.name ? 'checked' : ''}`}>{selected?.name === lead.name && <Icon name="check" size={13}/>}</span><strong>{lead.name}</strong><span className="country"><span>{lead.flag}</span>{lead.country}</span><span>{lead.type}</span><Status status={lead.status}/><span className="more">···</span></button>) : <div className="empty-results">{remoteLeads.length ? '这次没有找到合格客户，请换一组条件' : '搜索后，合格客户会显示在这里'}</div>}</div><div className="table-footer"><span>当前显示 {filteredLeads.length} 个客户</span></div></div>
          <aside className={`detail-panel panel ${filteredLeads.length && activeLead ? '' : 'detail-empty'}`}>{filteredLeads.length && activeLead ? <><div className="detail-top"><div className="company-symbol">◎</div><div className="company-title"><div><h2>{activeLead.name} <a href={activeLead.website} target="_blank" rel="noreferrer"><Icon name="external" size={14}/></a></h2><p>{activeLead.country} <i/> {activeLead.type} <i/> {activeLead.research ? '已完成官网背调' : '资料待整理'}</p></div><Status status={activeLead.status}/></div></div><div className="detail-tabs">{['概览', '来源证据', '邮件草稿'].map((tab) => <button className={detailTab === tab ? 'active' : ''} key={tab} onClick={() => setDetailTab(tab)}>{tab}</button>)}</div>{detailTab === '概览' && <><Overview lead={activeLead} onEvidence={() => setDetailTab('来源证据')} onDraft={() => setDetailTab('邮件草稿')}/><ResearchPanel lead={activeLead} loading={researchLoading} onStart={startResearch} onReview={reviewResearchField}/><LeadTimeline lead={activeLead} events={activeLead.auditEvents} onTransition={transitionLead} loading={leadTransitionLoading}/></>} {detailTab === '来源证据' && <Evidence lead={activeLead} onRefresh={refreshContacts} refreshing={contactRefreshLoading}/>} {detailTab === '邮件草稿' && <><Draft lead={activeLead} language={language} setLanguage={setLanguage} translatedDraft={translatedDraft} translationLoading={translationLoading} onTranslate={translateDraft} onReview={reviewDraft} reviewLoading={reviewLoading} status={draftStatus} setStatus={setDraftStatus} notify={notify}/><ContactForm lead={activeLead} onUpdate={updateContact} onRefresh={refreshContacts} refreshing={contactRefreshLoading}/><DraftGenerator lead={activeLead} taskConfig={remoteTaskConfig} loading={reviewLoading} onGenerate={generateDraft}/><ReviewControls lead={activeLead} sendingEnabled={mailboxStatus?.sending_enabled} onReview={reviewDraft} onSafetyCheck={runSendSafetyCheck} safetyLoading={safetyLoading} safetyResult={sendSafety} onSend={sendDraft} sendLoading={sendLoading} loading={reviewLoading}/></>}</> : <div className="detail-empty-state"><strong>没有选中的客户</strong><span>调整搜索词后选择一条客户记录</span></div>}</aside>
        </section>
      </>}
      </div>
    </main>
    {toast && <div className="toast"><span>✓</span>{toast}</div>}
    {showTask && <div className="modal-backdrop" onClick={() => setShowTask(false)}><form className="task-modal" onSubmit={createTask} onClick={(event) => event.stopPropagation()}><button type="button" className="modal-close" onClick={() => setShowTask(false)}>×</button><span className="modal-icon"><Icon name="search"/></span><h2>开始找客户</h2><p>只填写这次搜索需要的条件，系统会自动保存设置。</p><input type="hidden" name="name" value="默认获客工作区" readOnly/><label>产品或业务<input name="product" placeholder="例如：注塑件、精密零件" /></label><label>关键词（逗号分隔）<input name="keywords" placeholder="例如：塑料件、产品制造商、采购" /></label><div className="modal-grid"><label>目标国家 / 地区<input name="countries" placeholder="例如：德国、墨西哥" /></label><label>行业<input name="industries" placeholder="例如：汽车、电子" /></label></div><button type="submit" className="primary-button full">进入搜索 <Icon name="arrow" size={16}/></button></form></div>}
    {showRuleEditor && remoteTaskConfig && <RuleEditorModal task={remoteTaskConfig} onClose={() => setShowRuleEditor(false)} onSave={saveCriteria}/>}
    {showBrowserImport && (
      <BrowserImportModal onClose={() => setShowBrowserImport(false)} onImport={importBrowserResults} loading={browserImportLoading}/>
    )}
  </div>
}

function mapRemoteLead(item) {
  const lead = item.lead
  return {
    name: lead.company_name,
    country: lead.country && lead.country !== 'unknown' ? lead.country : '暂无公开国家信息',
    flag: '·',
    type: customerTypeLabel(lead.customer_type),
    score: item.score?.total > 0 ? item.score.total : null,
    status: item.qualified ? (lead.quality === 'complete' ? 'evidence' : 'review') : 'review',
    workflowStatus: lead.status || 'new',
    detail: '已找到官网公开邮箱，可开始核验客户资料。',
    email: lead.emails?.[0] || '未发现公开邮箱',
    emails: lead.emails || [],
    website: lead.website || `https://${lead.domain}`,
    domain: lead.domain,
    evidenceLevel: lead.evidence_level || 'none',
    identityConsistency: lead.identity_consistency || { score: 0, status: 'unknown', matched_tokens: [], reason: 'no_same_domain_evidence' },
    sourceSummary: lead.source_summary || { website_count: 0, same_domain_count: 0, external_count: 0, external_status: 'none' },
    evidenceChecks: lead.evidence_checks || {},
    flags: lead.flags || [],
    isRemote: true,
    qualified: Boolean(item.qualified),
    contacted: Boolean(item.contacted),
    rejectionReasons: item.rejection_reasons?.length ? item.rejection_reasons : fallbackRejectionReasons(lead),
  }
}

function fallbackRejectionReasons(lead) {
  const reasons = []
  if (!lead.website && !lead.domain) reasons.push('missing_website')
  if (!lead.emails?.length) reasons.push('missing_public_email')
  return reasons
}

function rejectionReasonLabel(reason) {
  return { missing_website: '缺少官网', missing_public_email: '没有官网公开邮箱', missing_website_evidence: '缺少官网来源证据', missing_product_evidence: '缺少官网产品证据', score_below_threshold: '评分低于门槛', conflicting_country: '国家来源冲突', country_not_target: '不属于目标国家/地区', country_unconfirmed: '国家/地区未能核验', qualified_quota_exceeded: '超过合格客户配额', email_domain_mismatch: '邮箱域名与官网不同', company_identity_unconfirmed: '官网未确认公司名' }[reason] || reason
}

function reviewFlagLabel(flag) {
  return { conflicting_country: '国家来源冲突', email_domain_mismatch: '邮箱域名与官网不同', company_identity_unconfirmed: '官网未确认公司主体', invalid_email: '邮箱格式无效', missing_website: '缺少官网' }[flag] || flag
}

function identityConsistencyLabel(signal) {
  return { strong: '主体信号较强', partial: '主体信号部分匹配', weak: '主体信号较弱', unknown: '暂无同域证据' }[signal] || signal
}

function customerTypeLabel(value) {
  return { retailer: '零售商', distributor: '分销商', wholesaler: '批发商', manufacturer: '制造商', consumer: '终端客户', service_provider: '服务商', unknown: '暂无公开类型信息' }[value] || '暂无公开类型信息'
}

function evidenceLevelLabel(value) {
  return { multi_source: '多来源核验', single_source: '单一官网来源', search_only: '仅搜索来源', none: '暂无来源' }[value] || '暂无来源'
}

function evidenceCheckLabel(key) {
  return { company_name: '公司名', country: '国家', email: '邮箱', product: '产品', industry: '行业' }[key] || key
}

function evidenceCheckStatus(value) {
  return { supported: '已找到', not_found: '未找到', not_configured: '未设置', not_checked: '未检查', conflicting: '信息不一致' }[value] || value
}

function DiscoveryFunnel({ summary, visibleCount }) {
  const count = Number.isFinite(visibleCount) ? visibleCount : (summary?.qualified_count || 0)
  return <div className="discovery-funnel simple-funnel"><div><strong>当前条件下</strong><span>可发送客户</span></div><div className="qualified-result-count"><b>{count}</b><span>家</span></div><p className="funnel-note">这些客户已找到官网公开邮箱，可以直接进入人工发送。其他搜索条件的客户仍保存在本机数据库。</p></div>
}

function Metric({ icon, label, value, note }) { return <div className="metric"><span className={`metric-icon ${icon}`}><Icon name={icon === 'researching' ? 'users' : icon} size={20}/></span><div><span>{label}</span><strong>{value}<Icon name="arrow" size={16}/></strong><small>{note}</small></div></div> }
function ReplyCenter({ mailboxStatus, threads, analyses, followUpTasks, loading, onTest, onSync, onAnalyze, onGenerateDraft, onFollowUpStatus }) {
  const humanReview = analyses.filter((item) => item.needs_human_review).length
  const analyzableThreads = threads.filter((thread) => !thread.is_system_notification)
 return <section className="reply-center panel"><div className="reply-center-heading"><div><h2>收件与回复 <span>{threads.length} 封来信 · {analyses.length} 条分析</span></h2><p>{mailboxStatus?.configured ? '阿里邮箱已连接' : '阿里邮箱未配置'}</p></div><div className="reply-actions"><button className="outline-button" disabled={loading || !mailboxStatus?.configured} onClick={onTest}>测试连接</button><button className="outline-button" disabled={loading || !mailboxStatus?.configured} onClick={onSync}>同步收件箱</button><button className="primary-button" disabled={loading || !analyzableThreads.length} onClick={onAnalyze}>{loading ? '处理中…' : '分析来信'}</button></div></div>{threads.length ? <><div className="reply-summary"><span>需要关注 {humanReview} 条</span>{analyses.length ? <span>已生成建议</span> : <span>待分析</span>}<span>跟进事项 {followUpTasks.length} 条</span></div><div className="reply-list">{threads.map((thread) => { const analysis = analyses.find((item) => item.message_id === thread.message_id); const followUp = followUpTasks.find((item) => item.message_id === thread.message_id); return <article className="reply-item" key={thread.message_id}><div><strong>{thread.from_email || '未知发件人'}</strong><span>{thread.subject || '无主题'}{thread.is_bounce ? ' · 退信' : ''}{thread.is_system_notification ? ' · 系统通知' : ''}</span></div>{analysis ? <div className="reply-analysis"><b>{replyCategoryLabel(analysis.category)}</b><span>{(analysis.confidence * 100).toFixed(0)}% · {analysis.risk_level === 'high' ? '高风险' : analysis.risk_level === 'medium' ? '中风险' : '低风险'}</span><p>{analysis.suggested_action}{analysis.needs_human_review ? ' · 建议人工确认' : ''}</p>{followUp && <label className="follow-up-status">跟进状态：<select value={followUp.status} onChange={(event) => onFollowUpStatus(followUp.id, event.target.value)}><option value="open">待处理</option><option value="in_progress">处理中</option><option value="completed">已完成</option><option value="cancelled">已取消</option></select></label>}<button className="outline-button" disabled={loading} onClick={() => onGenerateDraft(thread.message_id)}>生成跟进草稿</button></div> : <em>待分析</em>}</article> })}</div></> : <div className="reply-empty"><strong>当前没有来信</strong><span>收到客户回复后，内容会显示在这里。</span></div>}</section>
}

function replyCategoryLabel(category) { return { interested: '有意向', pricing: '询价', delivery: '交期/物流', complaint: '投诉', bounce: '退信', not_interested: '暂不考虑', other: '其他' }[category] || category }
function CustomFieldResults({ research, onReview }) {
  const fields = Object.entries(research?.custom_fields || {}).filter(([, field]) => field?.status !== 'unknown' && String(field?.value || '').trim())
  if (!fields.length) return null
  const statusLabel = { verified: '已确认', reported: '来源信息', conflicting: '信息不一致', unknown: '暂无公开信息' }
  const labels = { company_identity: '公司主体信息', official_contact_channels: '官网与联系方式', business_positioning: '主营产品与业务定位', industry_business_fit: '行业与业务需求匹配', procurement_decision_makers: '采购与决策层信息', historical_sourcing_categories: '过往采购品类' }
  return <div className="custom-field-results"><div className="section-title"><h3>客户资料</h3><span className="evidence-count">{fields.length} 项</span></div><div className="custom-field-list">{fields.map(([key, field]) => <div className="custom-field-row" key={key}><div className="custom-field-main"><strong>{labels[key] || key}</strong><span className={`custom-field-status ${field.status}`}>{statusLabel[field.status] || field.status}</span></div><p>{field.status === 'unknown' ? '当前公开来源未能确认' : field.value || '未填写'}</p><div className="custom-field-meta"><span>置信度 {Math.round((field.confidence || 0) * 100)}%</span>{field.sources?.length ? <span>{field.sources.map((source) => <a href={source} target="_blank" rel="noreferrer" key={source}>{source}<Icon name="external" size={11}/></a>)}</span> : <span>暂无来源</span>}</div>{onReview && field.status !== 'verified' && field.sources?.length > 0 && <button className="outline-button custom-field-review" onClick={() => onReview(key, field.value)}>确认字段</button>}</div>)}</div></div>
}

function ResearchPanel({ lead, loading, onStart, onReview }) {
  const [sourceUrl, setSourceUrl] = useState(lead.website || '')
  const [maxAttempts, setMaxAttempts] = useState('2')
  const [requestKey, setRequestKey] = useState('')
  const reviewer = '本地用户'
  const run = lead.researchRun
  const running = run?.status === 'running'
  return <div className="review-controls research-panel"><CustomFieldResults research={lead.research} onReview={(key, value) => onReview(key, value, reviewer)}/><div className="section-title"><h3>资料核验</h3><span>{run?.status === 'running' ? '正在核验' : run?.status === 'failed' ? '核验失败' : lead.research ? '已完成核验' : '资料待整理'}</span></div><p className="research-intro">系统会根据官网公开页面补充公司主体、联系方式、产品和采购信息，并保留来源。</p><label>字段复核人<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="填写姓名" /></label><label>来源网址<input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></label><button className="primary-button full" disabled={loading || running || !sourceUrl.trim()} onClick={() => onStart(sourceUrl.trim(), Number(maxAttempts), requestKey.trim())}>{loading ? '提交中…' : running ? '正在核验…' : run?.status === 'failed' ? '重新核验客户资料' : '开始核验客户资料'} <Icon name="arrow" size={16}/></button>{run?.error && <p className="generator-hint">核验未完成：请检查官网是否可以访问。</p>}{['succeeded', 'review_required'].includes(run?.status) && <p className="research-success">客户资料已更新，请查看上方核验结果。</p>}<details className="maintenance-inline research-maintenance"><summary>维护：高级核验设置</summary><div className="research-fields"><label>最大尝试次数<select value={maxAttempts} onChange={(event) => setMaxAttempts(event.target.value)}><option value="1">1 次</option><option value="2">2 次</option><option value="3">3 次</option></select></label><label>请求标识（维护用）<input value={requestKey} onChange={(event) => setRequestKey(event.target.value)} placeholder="留空即可" /></label></div></details></div>
}

function researchStepLabel(step) { return { queued: '排队中', fetching: '抓取官网', analyzing: '分析内容', scoring: '计算评分', persisting: '保存报告', completed: '已完成', failed: '失败' }[step] || step }
function discoveryStepLabel(step) { return { queued: '排队中', searching: '搜索候选', enriching: '核验官网', assessing: '筛选评分', completed: '已完成', failed: '失败' }[step] || step }
 function SendHistory({ history = [] }) {
   return <div className="send-history"><div className="section-title"><h3>联系记录</h3><span>{history.length ? `最近 ${history.length} 条` : '暂无发送记录'}</span></div>{history.length ? <div className="send-history-list">{history.slice().reverse().map((item) => <div className="send-history-item" key={item.id}><div><strong>{item.status === 'sent' ? '已发送' : '发送失败'}</strong><span>{item.recipient_email}</span></div><time>{item.created_at ? new Date(item.created_at).toLocaleString('zh-CN', { hour12: false }) : '时间未知'}</time>{item.error && <p>{item.error}</p>}</div>)}</div> : <p className="send-history-empty">邮件发送后，最近联系结果会显示在这里。</p>}</div>
 }

 function Overview({ lead, onEvidence, onDraft }) {
   const research = lead.research
   const products = research?.products?.length ? research.products.join('、') : ''
   const industry = research?.custom_fields?.industry_business_fit?.value || ''
   const market = research?.country || (lead.country && lead.country !== 'unknown' ? lead.country : '')
   const publicEmails = lead.emails?.length ? lead.emails.join('、') : ''
   const externalNote = lead.sourceSummary.external_status === 'linked_requires_review' ? ' · 外部来源待人工确认' : ''
   return <div className="detail-body"><h3>公司概览</h3><dl><dt>官网</dt><dd><a href={lead.website} target="_blank" rel="noreferrer">{lead.website.replace('https://', '').replace(/\/$/, '')}<Icon name="external" size={13}/></a></dd><dt>公开联系邮箱</dt><dd>{publicEmails}</dd><dt>行业 / 业务匹配</dt><dd>{industry}</dd><dt>公司规模</dt><dd>公开来源未提供</dd><dt>主要市场</dt><dd>{market} {research?.country_conflict && <span className="custom-field-status conflicting">来源冲突，需复核</span>}</dd><dt>产品</dt><dd>{products}</dd><dt>简介</dt><dd>{research?.business_summary || '暂无公开公司简介。'}</dd></dl><div className="section-divider"/><div className="section-title"><h3>来源证据</h3><span className={`evidence-level evidence-level-${lead.evidenceLevel}`}>{evidenceLevelLabel(lead.evidenceLevel)}</span><button className="outline-button" onClick={onEvidence}>查看来源 <Icon name="arrow" size={14}/></button></div><div className="evidence-mini"><span className="evidence-icon"><Icon name="clipboard" size={15}/></span><div><strong>官网背调来源</strong><p>{research?.evidence_url || '暂无来源信息'}</p><small>{lead.sourceSummary.same_domain_count || 0} 个同域来源 · {lead.sourceSummary.external_count || 0} 个外部关联来源{externalNote}</small></div><time>{research ? `置信度 ${(research.confidence * 100).toFixed(0)}%` : '资料待整理'}</time></div><div className="section-divider"/><div className="section-title"><h3>邮件草稿</h3><button className="text-button" onClick={onDraft}>查看详情 <Icon name="arrow" size={14}/></button></div><div className="draft-snippet"><span className="draft-status-dot"/><div><strong>{lead.isRemote ? '待生成' : '待人工审核'}</strong><p>{lead.isRemote ? '客户资料准备好后即可生成' : '等待确认'}</p></div><Icon name="arrow" size={16}/></div><SendHistory history={lead.sendHistory}/></div>
 }
function LegacyEvidence({ lead, onRefresh, refreshing }) { const research = lead.research; const evidenceUrls = research?.evidence_urls?.length ? research.evidence_urls : research?.evidence_url ? [research.evidence_url] : []; const checks = Object.entries(lead.evidenceChecks || {}); const identity = lead.identityConsistency || {}; const reviewFlags = (lead.flags || []).map(reviewFlagLabel); return <div className="detail-body evidence-view"><div className="section-title"><h3>来源证据</h3><span className="evidence-count">{research ? `已保存 ${evidenceUrls.length} 条` : '未知'}</span><button className="outline-button" type="button" disabled={refreshing} onClick={onRefresh}>{refreshing ? '重新抓取中…' : '重新抓取官网联系人'}</button></div><p className="evidence-intro">以下内容来自公开页面，AI 结论只能作为建议，必须回到原始来源复核。</p>{reviewFlags.length > 0 && <div className="review-flag-banner"><strong>需人工复核</strong><span>{reviewFlags.join(' · ')}</span></div>}<div className={`identity-signal identity-signal-${identity.status || 'unknown'}`}><strong>公司主体一致性</strong><span>{identity.score ?? 0}/100 · {identityConsistencyLabel(identity.status || 'unknown')}</span><small>{identity.status === 'unknown' ? '未使用搜索摘要或外部页面推断主体。' : '基于公司名、域名与同域官网正文的确定性匹配信号，不等于工商真实性证明。'}</small></div>{checks.length > 0 && <div className="evidence-checks"><strong>字段核验</strong><div>{checks.map(([key, value]) => <span className={`evidence-check evidence-check-${value}`} key={key}><b>{evidenceCheckLabel(key)}</b>{evidenceCheckStatus(value)}</span>)}</div></div>}{research ? <div className="timeline">{evidenceUrls.map((url, index) => <div className="timeline-item" key={url}><span className="timeline-dot"><Icon name="clipboard" size={13}/></span><div><time>{index === 0 ? `置信度 ${(research.confidence * 100).toFixed(0)}%` : '补充来源'}</time><strong>{index === 0 ? '官网背调来源' : '补充公开来源'}</strong><p>{index === 0 ? research.business_summary || '尚未保存背调摘要。' : '该来源用于交叉核验研究结论。'}</p><a href={url} target="_blank" rel="noreferrer">打开来源 <Icon name="external" size={12}/></a></div></div>)}</div> : <div className="timeline"><div className="timeline-item"><span className="timeline-dot"><Icon name="clipboard" size={13}/></span><div><strong>暂无来源信息</strong></div></div></div>}</div> }

function Evidence({ lead, onRefresh, refreshing }) {
  const research = lead.research
  const evidenceUrls = research?.evidence_urls?.length ? research.evidence_urls : research?.evidence_url ? [research.evidence_url] : []
  const checks = Object.entries(lead.evidenceChecks || {})
  const identity = lead.identityConsistency || {}
  const reviewFlags = (lead.flags || []).map(reviewFlagLabel)
  return <div className="detail-body evidence-view">
    <div className="section-title"><h3>信息来源</h3><span className="evidence-count">{research ? `已保存 ${evidenceUrls.length} 条` : '尚未核验'}</span></div>
    <p className="evidence-intro">以下信息来自公开页面，发送前可以打开原文进行确认。</p>
    <details className="maintenance-inline"><summary>维护：重新检查联系方式</summary><button className="outline-button" type="button" disabled={refreshing} onClick={onRefresh}>{refreshing ? '检查中…' : '重新检查联系方式'}</button></details>
    {reviewFlags.length > 0 && <div className="review-flag-banner"><strong>需要确认</strong><span>{reviewFlags.join(' · ')}</span></div>}
    <div className={`identity-signal identity-signal-${identity.status || 'unknown'}`}><strong>公司与官网匹配度</strong><span>{identity.score ?? 0}/100 · {identityConsistencyLabel(identity.status || 'unknown')}</span><small>{identity.status === 'unknown' ? '暂时没有足够的同域官网信息。' : '根据公司名称、域名和官网内容进行匹配，不代表工商登记证明。'}</small></div>
    {checks.length > 0 && <div className="evidence-checks"><strong>资料核验情况</strong><div>{checks.map(([key, value]) => <span className={`evidence-check evidence-check-${value}`} key={key}><b>{evidenceCheckLabel(key)}</b>{evidenceCheckStatus(value)}</span>)}</div></div>}
    {research ? <div className="timeline">{evidenceUrls.map((url, index) => <div className="timeline-item" key={url}><span className="timeline-dot"><Icon name="clipboard" size={13}/></span><div><time>{index === 0 ? `信息可信度 ${(research.confidence * 100).toFixed(0)}%` : '补充来源'}</time><strong>{index === 0 ? '官网来源' : '其他公开来源'}</strong><p>{index === 0 ? research.business_summary || '暂无公司简介。' : '该来源用于交叉确认信息。'}</p><a href={url} target="_blank" rel="noreferrer">打开来源 <Icon name="external" size={12}/></a></div></div>)}</div> : <div className="timeline"><div className="timeline-item"><span className="timeline-dot"><Icon name="clipboard" size={13}/></span><div><strong>完成客户资料核验后显示来源</strong></div></div></div>}
  </div>
}
function researchDraftState(lead) {
  const status = lead.researchRun?.status
  if (lead.research) return { title: '资料已整理', message: '客户资料已整理完成，可以生成邮件。', evidence: '邮件内容将基于已整理的客户资料生成。' }
  if (status === 'running' || status === 'queued') return { title: '资料整理中', message: '系统正在整理官网资料，完成后即可生成邮件。', evidence: '官网资料整理完成后生成邮件内容。' }
  if (status === 'failed') return { title: '资料整理未完成', message: '官网资料暂时没有整理完成，请稍后重新检查。', evidence: '资料整理完成后生成邮件内容。' }
  return { title: '等待资料整理', message: '系统会自动整理客户资料，完成后即可生成邮件。', evidence: '客户资料整理完成后生成邮件内容。' }
}

function Draft({ lead, language, setLanguage, translatedDraft, translationLoading, onTranslate }) { const draft = lead.draft; const researchState = researchDraftState(lead); const isDraftAvailable = Boolean(draft) || !lead.isRemote; const useTranslation = Boolean(draft && language === '中文' && translatedDraft); const body = useTranslation ? translatedDraft.body : draft?.body || (!isDraftAvailable ? '邮件内容将在客户资料整理完成后生成。' : language === '中文' ? `您好，${lead.name} 团队：\n\n我们是一家专注于便携式太阳能发电机及相关配件的中国制造商。了解到贵司在德国市场提供太阳能产品，我们想与您探讨产品目录是否有互补的机会。\n\n如果方向合适，我可以发送产品资料供您参考。` : `Hello ${lead.name} team,\n\nWe are a Chinese manufacturer focused on portable solar generators and related accessories. We noticed that your company offers solar products in Germany and would like to explore whether our product range could complement your current offering.\n\nIf relevant, I would be happy to share our product catalogue for your review.`); const recipient = draft?.recipient_email || (lead.email && lead.email.includes('@') ? lead.email : '未发现公开邮箱'); const subject = useTranslation ? translatedDraft.subject : draft?.subject || (isDraftAvailable ? (language === '中文' ? '关于便携式太阳能产品合作' : 'Portable solar products for your range') : researchState.title); const currentStatus = draft?.status === 'approved' ? 'approved' : draft?.status === 'revision_required' ? 'revision' : 'pending'; const draftLabel = draft?.kind === 'reply' ? '客户跟进草稿' : '首次邮件草稿'; const reviewHint = draft?.kind === 'reply' ? '基于客户来信和客户资料生成，发送前请人工确认' : '发送前请人工确认收件人与正文'; const evidenceHint = draft?.kind === 'reply' ? `内容基于客户来信及 ${draft.evidence_urls?.length || 0} 条来源` : `内容基于 ${draft?.evidence_urls?.length || 0} 条来源`; return <div className="detail-body draft-view"><div className="section-title"><h3>{draftLabel}</h3>{draft ? <div className="language-toggle"><button className={language === 'EN' ? 'active' : ''} onClick={() => setLanguage('EN')}>EN</button><button className={language === '中文' ? 'active' : ''} onClick={() => { setLanguage('中文'); if (!translatedDraft) onTranslate() }}>{translationLoading ? '翻译中…' : '中文预览'}</button></div> : isDraftAvailable && <div className="language-toggle">{['中文', 'EN'].map((item) => <button key={item} className={language === item ? 'active' : ''} onClick={() => setLanguage(item)}>{item}</button>)}</div>}</div><div className="review-banner"><span className="review-pulse"/><div><strong>{draft ? (currentStatus === 'approved' ? '已批准' : currentStatus === 'revision' ? '需修改' : '待人工审核') : researchState.title}</strong><p>{draft ? (useTranslation ? '中文仅用于阅读预览，英文邮件内容未修改' : reviewHint) : researchState.message}</p></div></div><div className="email-preview"><div className="email-meta"><span>收件人</span><strong>{recipient}</strong></div><div className="email-meta"><span>主题</span><strong>{subject}</strong></div><div className="email-copy">{body.split('\n').map((line, index) => <p key={`${line}-${index}`}>{line || '\u00a0'}</p>)}</div><div className="evidence-tag"><Icon name="clipboard" size={13}/>{draft ? evidenceHint : researchState.evidence}</div></div></div> }

function ContactForm({ lead, onUpdate, onRefresh, refreshing }) {
  const [email, setEmail] = useState('')
  const [sourceUrl, setSourceUrl] = useState(lead.website || '')
  const [sourceExcerpt, setSourceExcerpt] = useState('')
  if (!lead.isRemote || lead.draft) return null
  return <div className="review-controls contact-form"><div className="section-title"><h3>联系人资料</h3><span>系统会自动整理官网公开联系方式</span></div>{!lead.email?.includes('@') && <details className="maintenance-inline"><summary>维护：重新检查或补充联系方式</summary><button type="button" className="outline-button full" disabled={refreshing} onClick={onRefresh}>{refreshing ? '检查中…' : '重新检查联系方式'}</button><p className="generator-hint">仅在自动整理未找到邮箱时使用；补充内容必须来自公开页面。</p><label>公开邮箱<input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="例如：sales@example.com" /></label><label>来源网址<input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="公开页面 URL" /></label><label>来源说明<textarea value={sourceExcerpt} onChange={(event) => setSourceExcerpt(event.target.value)} placeholder="例如：官网 Contact 页面展示该邮箱" rows="2" /></label><button className="outline-button full" disabled={!email.trim() || !sourceUrl.trim() || !sourceExcerpt.trim()} onClick={() => onUpdate(email, sourceUrl, sourceExcerpt)}>保存联系人证据</button></details>}</div>
}

function SenderProfileEditor({ taskConfig, onSave }) {
  const profile = taskConfig?.sender_profile || {}
  const [companyName, setCompanyName] = useState(profile.company_name || '')
  const [contactName, setContactName] = useState(profile.contact_name || '')
  const [position, setPosition] = useState(profile.position || '')
  return <div className="review-controls sender-editor"><div className="section-title"><h3>发件人资料</h3><span>用于下一版草稿</span></div><label>公司名称<input value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="例如：ABC Trading Co., Ltd." /></label><label>联系人姓名<input value={contactName} onChange={(event) => setContactName(event.target.value)} placeholder="例如：Li Ming" /></label><label>职位<input value={position} onChange={(event) => setPosition(event.target.value)} placeholder="例如：Sales Manager" /></label><button className="outline-button full" onClick={() => onSave({ company_name: companyName, contact_name: contactName, position })}>保存发件人资料</button></div>
}

function SenderProfilePage({ taskConfig, onSave }) {
  return <div className="settings-page"><div className="page-heading"><div><h1>发件人资料</h1><p>统一用于自动生成邮件，保存后新邮件会自动使用。</p></div><span className="database-local-badge">本机保存</span></div><div className="settings-content"><SenderProfileEditor taskConfig={taskConfig} onSave={onSave}/><div className="settings-tip"><strong>使用说明</strong><p>只需要填写一次。系统会把公司名称、联系人姓名和职位带入后续邮件，不需要逐封重复填写。</p></div></div></div>
}

function SettingsPanel({ status, mailboxStatus }) {
  const badge = (ready, enabled = ready) => enabled ? ['已就绪', 'ready'] : ['未配置', 'pending']
  const [deepseekLabel, deepseekTone] = badge(status?.deepseek_configured)
  const [imapLabel, imapTone] = badge(status?.ali_imap_configured || mailboxStatus?.configured)
  const [smtpLabel, smtpTone] = badge(status?.ali_smtp_enabled, status?.ali_smtp_enabled)
  return <div className="settings-page"><div className="page-heading"><div><h1>设置</h1><p>管理 AI 和邮箱连接状态。账号、密码和 API Key 不会显示在页面中。</p></div></div><div className="settings-grid"><section className="settings-card panel"><div className="section-title"><h2>DeepSeek</h2><span className={`settings-status ${deepseekTone}`}><i/>{deepseekLabel}</span></div><p>用于整理客户资料、核验公开信息和自动生成邮件。</p><div className="settings-row"><span>配置文件</span><strong>{status?.config_path || 'config/.env'}</strong></div><div className="settings-row"><span>API Key</span><strong>已隐藏</strong></div></section><section className="settings-card panel"><div className="section-title"><h2>阿里邮箱</h2><span className={`settings-status ${imapTone}`}><i/>{imapLabel}</span></div><p>用于读取收件箱。当前收件功能保持只读，不会自动发送邮件。</p><div className="settings-row"><span>IMAP 收件</span><strong>{imapLabel}</strong></div><div className="settings-row"><span>SMTP 发信</span><strong className={`settings-value ${smtpTone}`}>{smtpLabel === '已就绪' ? '已开启' : '未开启'}</strong></div></section></div><div className="settings-guide panel"><strong>需要修改配置？</strong><p>编辑项目中的 <code>config/.env</code>，保存后重启本地服务。密码和 API Key 只放在本机配置文件中，不要提交到 Git。</p></div></div>
}

function DraftGenerator({ lead, taskConfig, loading, onGenerate }) {
  const [product, setProduct] = useState(taskConfig?.criteria?.product || '')
  const [template, setTemplate] = useState('Introduce {product} to {company} based on their published product range.')
  const [autoStarted, setAutoStarted] = useState(false)
  useEffect(() => {
    const profile = taskConfig?.sender_profile || {}
    const ready = Boolean(lead.isRemote && lead.research && lead.email?.includes('@') && !lead.draft && product.trim() && profile.company_name?.trim() && profile.contact_name?.trim() && profile.position?.trim())
    if (ready && !autoStarted && !loading) {
      setAutoStarted(true)
      onGenerate(template, product.trim())
    }
  }, [lead.isRemote, lead.domain, lead.research, lead.email, lead.draft, product, template, taskConfig?.sender_profile, autoStarted, loading, onGenerate])
  if (!lead.isRemote) return null
  const hasRecipient = Boolean(lead.email?.includes('@'))
  const researchState = researchDraftState(lead)
  if (!lead.draft) return <div className="review-controls draft-generator"><div className="section-title"><h3>邮件生成</h3><span>{autoStarted ? '正在自动生成' : '等待条件满足'}</span></div><p className="generator-hint">填写并保存统一发件人资料后，系统会根据客户资料自动生成邮件并进入审核。</p>{!hasRecipient && <p className="generator-hint">当前客户没有公开邮箱，暂不生成邮件。</p>}{!lead.research && <p className="generator-hint">客户资料整理完成后自动生成。</p>}</div>
  if (lead.draft) return <div className="review-controls draft-generator"><div className="section-title"><h3>邮件生成</h3><span>已自动生成</span></div><p className="generator-hint">邮件已根据客户资料和统一发件人资料生成，请在上方查看中文预览后进行审核。</p></div>
  return <div className="review-controls draft-generator"><div className="section-title"><h3>{lead.draft ? '重新生成邮件' : '生成邮件'}</h3><span>{lead.draft ? '会创建新版本，不覆盖当前草稿' : '使用已整理的客户资料与发件人资料'}</span></div><label>产品或服务<input value={product} onChange={(event) => setProduct(event.target.value)} placeholder="填写本次推广产品" /></label><label>写作方向<textarea value={template} onChange={(event) => setTemplate(event.target.value)} rows="2" /></label><button className="primary-button full" disabled={loading || !product.trim() || !lead.research || !hasRecipient} onClick={() => onGenerate(template, product)}>{loading ? '生成中…' : lead.draft ? '生成新版本草稿' : '生成邮件草稿'} <Icon name="arrow" size={16}/></button>{!hasRecipient ? <p className="generator-hint">当前没有公开邮箱，补充收件人后才能生成。</p> : !lead.research && <p className="generator-hint">{researchState.message}</p>}</div>
}

function BatchMailPanel({ drafts, index, onIndexChange, reviewer = '', onReviewerChange = () => {}, selectedIds, onToggle, onReview, translations, translationLoading, onTranslate, onPreview, onConfirm, loading, preview }) {
  const current = drafts.length ? drafts[Math.min(index, drafts.length - 1)] : null
  const [showChinese, setShowChinese] = useState(false)
  useEffect(() => { if (current) setShowChinese(false) }, [current?.id])
  if (!current) return null
  const translated = translations?.[current.id]
  const displayedSubject = showChinese && translated ? translated.subject : current.subject
  const displayedBody = showChinese && translated ? translated.body : current.body
  const approved = drafts.filter((draft) => draft.status === 'approved')
  const selectedApproved = drafts.filter((draft) => selectedIds.includes(draft.id) && draft.status === 'approved')
  return <section className="batch-mail-panel panel"><div className="panel-heading"><div><h2>批量审核邮件 <span>{drafts.length} 封</span></h2><p>手动查看下一封，审核通过后选择要发送的邮件</p></div><span className="database-readonly">已批准 {approved.length} 封</span></div><div className="batch-mail-toolbar"><label>审核人<input value={reviewer} onChange={(event) => onReviewerChange(event.target.value)} placeholder="填写姓名" /></label><span>已选择 {selectedIds.length} 封 · 可发送 {selectedApproved.length} 封</span><button type="button" className="send-button" disabled={loading || !selectedApproved.length} onClick={onPreview}>批量发送已选邮件</button></div><div className="batch-mail-carousel"><button type="button" className="carousel-arrow" disabled={index <= 0} onClick={() => onIndexChange(index - 1)} aria-label="上一封">‹</button><article className="batch-mail-card"><div className="batch-mail-card-top"><span>第 {index + 1} / {drafts.length} 封</span><span className={`batch-draft-status ${current.status}`}>{current.status === 'approved' ? '已批准' : current.status === 'rejected' ? '已拒绝' : current.status === 'revision_required' ? '需修改' : '待审核'}</span></div><div className="batch-mail-recipient"><strong>{current.recipient_email}</strong><button type="button" className="text-button" disabled={translationLoading} onClick={() => translated ? setShowChinese((value) => !value) : onTranslate(current.id)}>{translationLoading ? '翻译中…' : showChinese ? '返回英文' : '中文预览'}</button></div><b>{displayedSubject}</b><p>{displayedBody}</p>{showChinese && translated && <small className="translation-note">中文仅供审核阅读，实际发送仍使用英文邮件。</small>}<label className="batch-select"><input type="checkbox" checked={selectedIds.includes(current.id)} disabled={current.status !== 'approved'} onChange={() => onToggle(current.id)} />加入批量发送</label><div className="batch-card-actions"><button type="button" className="outline-button" disabled={loading || current.status === 'approved' || current.status === 'rejected'} onClick={() => onReview(current.id, 'approve')}>审核通过</button><button type="button" className="outline-button" disabled={loading || current.status === 'approved' || current.status === 'rejected'} onClick={() => onReview(current.id, 'request-revision')}>退回修改</button></div></article><button type="button" className="carousel-arrow" disabled={index >= drafts.length - 1} onClick={() => onIndexChange(index + 1)} aria-label="下一封">›</button></div>{preview && <div className="batch-send-confirm"><strong>确认发送已选的 {preview.count} 封邮件？</strong><p>系统会逐封检查并记录发送结果，未批准的邮件不会发送。</p><button type="button" className="outline-button" onClick={() => onConfirm()}>确认发送</button></div>}</section>
}

function ReviewControls({ lead, sendingEnabled, onReview, onSafetyCheck, safetyLoading, safetyResult, onSend, sendLoading, loading }) {
  return null
  const [reviewer, setReviewer] = useState('')
  const [note, setNote] = useState('')
  const [confirmingSend, setConfirmingSend] = useState(false)
  if (!lead.draft) return null
  const locked = loading || lead.draft.status === 'approved' || lead.draft.status === 'rejected'
  const canSend = sendingEnabled && lead.draft.status === 'approved' && safetyResult?.allowed
  return <div className="review-controls"><div className="section-title"><h3>审核操作</h3><span>批准、检查和发送相互独立</span></div><label>审核人<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="填写姓名" /></label><label>处理意见<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="退回或拒绝时必填" rows="2" /></label><div className="review-control-actions"><button className="outline-button" disabled={safetyLoading} onClick={onSafetyCheck}>{safetyLoading ? '检查中…' : lead.draft.status === 'approved' ? '重新运行发送前检查' : '运行发送前检查'}</button><button className="outline-button" disabled={locked || !reviewer.trim() || !note.trim()} onClick={() => onReview('request-revision', note, reviewer)}>{loading ? '处理中…' : '退回修改'}</button><button className="primary-button" disabled={locked || !reviewer.trim()} onClick={() => onReview('approve', note, reviewer)}>批准草稿</button>{canSend && <button className="send-button" disabled={sendLoading} onClick={() => setConfirmingSend(true)}>{sendLoading ? '发送中…' : '发送邮件'}</button>}</div>{safetyResult && <div className={`send-safety-result ${safetyResult.allowed ? 'allowed' : 'blocked'}`}><strong>{safetyResult.allowed ? '检查通过' : '检查阻断'}</strong>{safetyResult.reasons?.length ? <ul>{safetyResult.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul> : <p>当前未发现配置层面的阻断原因，但发送前仍需人工确认。</p>}</div>}{confirmingSend && <div className="send-confirmation"><strong>确认发送这封邮件？</strong><p>收件人：{lead.draft.recipient_email}</p><p>主题：{lead.draft.subject}</p><span>此操作将通过阿里 SMTP 发出真实邮件。</span><div><button className="outline-button" onClick={() => setConfirmingSend(false)}>取消</button><button className="send-button" onClick={() => { setConfirmingSend(false); onSend() }}>确认发送</button></div></div>}</div>
}

function DatabasePanel({ overview, loading, exportLoading, onExport, onSelect, searchCountries }) {
  const [view, setView] = useState('all')
  const stats = overview?.stats || {}
  const items = overview?.items || []
  const targetCountries = splitSearchValues(searchCountries)
  const databaseNoise = ['weather', 'calculator', 'university', 'tripadvisor', 'hotels.com', '百度知道', '知乎', '站酷', 'google trends', 'google traductor', 'wikipedia', 'worldometer', 'population', 'quiz', 'whois', 'search -', 'search brand', 'search wiki', 'sign in', 'log on', 'login', 'google images', 'google scholar', 'yahoo mail', 'yahoo新闻', 'facebook share', 'steam workshop', 'tiktok', 'recipe', 'chicken noodle', 'gas station', 'gas prices', 'hotel ', 'hotels:', 'trivago', 'world time', 'time now', 'time converter', 'current time', 'aest time', 'm22759', 'honor magic', 'microsoft ', 'bing ', 'top cnc', 'top machining', 'medical suppliers', 'medical device distributors', 'importer & exporter search', 'global trade database', 'buy seafood', 'seafood market', 'cricket world cup', 'reading nook', 'convert cm', 'centimeters to feet', 'analysis of ', 'about montreal', 'on this day', 'today in history', 'markets today', 'marketwatch', 'markets insider', 'compare cheap flights', 'cheap hotel', 'billa plus', 'duolingo', 'world health organization', 'who)', 'target :', 'wish |', 'wish for', 'merchant support', 'merchant materials', 'door dash', 'doordash', 'little caesars', 'restaurant', 'restaurante', 'secretaría', 'universidad', 'definition', 'definición', 'empathique', 'humanidades', 'russland', 'russia map', 'map of russia', 'malouines', 'falklands', 'iron lung', 'ford ', 'lg ', 'coretec', 'avif', 'magic6', 'julián quiñones', 'soup recipe', 'power fx', 'github -', 'générez des styles', 'synchronize account', 'bank of america']
  const businessMarkers = ['cnc', 'machin', 'mold', 'mould', 'plastic', 'precision', 'injection', 'manufactur', 'tooling', 'medical', 'industrial', 'components', 'parts']
  const customerItems = items.filter((item) => {
    const name = String(item.lead?.company_name || '').trim().toLowerCase()
    const domain = String(item.lead?.domain || '').trim().toLowerCase()
    const identity = item.lead?.identity_consistency?.status
    const evidence = item.lead?.evidence_level
    const sources = item.lead?.source_summary || {}
    const sourceText = (item.lead?.sources || []).map((source) => String(source?.[1] || '')).join(' ').toLowerCase()
    const hasWebsiteEvidence = Number(sources.website_count || 0) > 0 && Number(sources.same_domain_count || 0) > 0
    const identityBacked = identity === 'strong' || identity === 'partial'
    const businessInIdentity = businessMarkers.some((marker) => `${name} ${domain}`.includes(marker))
    const businessInEvidence = businessMarkers.filter((marker) => sourceText.includes(marker)).length >= 2
    return name && hasWebsiteEvidence && identityBacked && evidence !== 'search_only' && (businessInIdentity || businessInEvidence) && !databaseNoise.some((marker) => name.includes(marker)) && !(domain && name === domain && !item.lead?.emails?.length && !item.lead?.country)
  })
  const displayItems = view === 'sendable' ? customerItems.filter((item) => item.sendable) : view === 'pending' ? customerItems.filter((item) => item.pending_contact) : view === 'contacted' ? customerItems.filter((item) => item.contacted) : view === 'follow_up' ? customerItems.filter((item) => item.follow_up_ready) : view === 'qualified' ? customerItems.filter((item) => item.qualified && !item.contacted) : customerItems
  const viewDescription = view === 'sendable' ? '今天优先联系这些客户，按每日发送安排' : view === 'pending' ? '这些客户符合条件，今天不发送，保留到后续联系' : view === 'contacted' ? '查看已经发送过邮件的客户' : view === 'follow_up' ? '查看收到回复、可以继续跟进的客户' : view === 'qualified' ? '展示所有符合当前条件的客户，不受每日发送数量影响' : '查看本机保存的客户资料；明显的文章、工具和目录结果已隐藏'
  return <>
    <div className="page-heading"><div><h1>客户资料库</h1><p>已找到的客户资料、公开邮箱和来源都会保存在本机</p></div><div className="database-heading-actions"><button className="outline-button" disabled={loading || exportLoading || !overview?.items?.length} onClick={onExport}>{exportLoading ? '导出中…' : '导出 Excel'}</button><span className="database-local-badge"><Icon name="database" size={16}/>本机保存</span></div></div>
    {loading && <div className="data-notice loading"><span />正在读取本地数据库…</div>}
    {!loading && !overview && <div className="empty-results">暂时无法读取本地数据库，请稍后重试。</div>}
    {overview && <>
      <div className="database-stats"><Metric icon="mail" label="今日发送范围" value={stats.sendable_count || 0} note="按每日发送安排"/><Metric icon="check" label="合格客户" value={stats.qualified_count || 0} note="符合当前搜索条件"/><Metric icon="users" label="待联系" value={stats.pending_contact_count || 0} note="合格但安排到后续"/><Metric icon="clipboard" label="已联系" value={stats.contacted_count || 0} note="已有发送记录"/></div>
      <section className="database-table panel"><div className="panel-heading"><div><h2>客户资料 <span>{displayItems.length} 条</span></h2><p>{viewDescription}</p></div><span className="database-readonly">本机资料</span></div><div className="database-view-tabs"><button className={view === 'sendable' ? 'active' : ''} onClick={() => setView('sendable')}>今日发送 {stats.sendable_count || 0}</button><button className={view === 'pending' ? 'active' : ''} onClick={() => setView('pending')}>待联系 {stats.pending_contact_count || 0}</button><button className={view === 'contacted' ? 'active' : ''} onClick={() => setView('contacted')}>已联系 {stats.contacted_count || 0}</button><button className={view === 'follow_up' ? 'active' : ''} onClick={() => setView('follow_up')}>可继续跟进 {stats.follow_up_count || 0}</button><button className={view === 'qualified' ? 'active' : ''} onClick={() => setView('qualified')}>合格客户 {stats.qualified_count || 0}</button><button className={view === 'all' ? 'active' : ''} onClick={() => setView('all')}>全部客户 {customerItems.length}</button></div><div className="database-table-head"><span>公司</span><span>国家 / 地区</span><span>公开邮箱</span><span>来源</span><span>状态</span></div><div className="database-list">{displayItems.length ? displayItems.map((item) => <button type="button" className="database-row" key={`${item.task_id}-${item.lead.domain}`} onClick={() => onSelect(item)} aria-label={`打开客户资料：${item.lead.company_name || item.lead.domain}`}><strong>{item.lead.company_name || item.lead.domain}</strong><span>{item.lead.country && item.lead.country !== 'unknown' ? item.lead.country : '国家待核验'}</span><span>{item.lead.emails?.length ? item.lead.emails.join(', ') : '未发现公开邮箱'}</span><span>{item.lead.source_summary?.website_count || 0} 个来源</span><span className={item.follow_up_ready ? 'database-qualified' : item.contacted ? 'database-sendable' : item.pending_contact ? 'database-pending' : item.qualified ? 'database-qualified' : 'database-pending'}>{item.follow_up_ready ? '可继续跟进' : item.contacted ? '已联系' : item.pending_contact ? '待联系' : item.qualified ? '合格客户' : item.sendable ? '今日发送' : '待完善'}</span></button>) : <div className="empty-results">当前分类还没有符合条件的客户。</div>}</div></section>
    </>}
  </>
}

export default App
function LeadTimeline({ lead, events, onTransition, loading }) {
  const transitionOptions = {
    new: ['cleaning', 'awaiting_score'],
    cleaning: ['awaiting_score', 'invalid'],
    awaiting_score: ['awaiting_review', 'selected', 'invalid'],
    awaiting_review: ['selected', 'invalid'],
    selected: ['contacted', 'paused', 'invalid'],
    contacted: ['replied', 'following_up', 'paused'],
    replied: ['following_up', 'converted', 'paused'],
    following_up: ['replied', 'converted', 'paused'],
    paused: ['selected', 'contacted', 'following_up'],
  }
  const [target, setTarget] = useState('awaiting_score')
  const [actor, setActor] = useState('')
  const [note, setNote] = useState('')
  const currentStatus = lead.workflowStatus || 'new'
  const options = transitionOptions[currentStatus] || []
  useEffect(() => {
    setTarget(options[0] || '')
    setActor('')
    setNote('')
  }, [lead.domain, currentStatus])
  return <details className="lead-timeline maintenance-inline"><summary>维护：客户状态记录</summary><div className="lead-timeline-body"><div className="section-title"><h3>客户状态记录</h3><span>当前：{workflowStatusLabel(currentStatus)} · {events.length} 条记录</span></div><div className="lead-transition"><select value={target} onChange={(event) => setTarget(event.target.value)} disabled={!options.length}>{options.length ? options.map((status) => <option value={status} key={status}>{workflowStatusLabel(status)}</option>) : <option value="">暂无可用流转</option>}</select><input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="操作人"/><input value={note} onChange={(event) => setNote(event.target.value)} placeholder="变更原因（可选）"/><button className="outline-button" disabled={loading || !options.length || !actor.trim()} onClick={() => onTransition(target, actor, note)}>{loading ? '保存中…' : options.length ? '更新状态' : '状态已结束'}</button></div>{events.length ? <div className="timeline-list">{events.map((event) => <div className="timeline-row" key={event.id}><strong>{workflowStatusLabel(event.from_status)} → {workflowStatusLabel(event.to_status)}</strong><span>{event.actor} · {new Date(event.occurred_at).toLocaleString()}</span>{event.note && <p>{event.note}</p>}</div>)}</div> : <p className="timeline-empty">客户状态暂时没有变化记录。</p>}</div></details>
}

function workflowStatusLabel(status) {
  return {
    new: '新客户', cleaning: '清洗中', awaiting_score: '待评分', awaiting_review: '待审核',
    selected: '已入选', contacted: '已联系', replied: '已回复', following_up: '跟进中',
    converted: '已转化', paused: '暂缓', invalid: '无效',
  }[status] || status || '未知状态'
}
