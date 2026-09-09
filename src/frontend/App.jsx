import { useEffect, useMemo, useState } from 'react'

const navItems = [
  ['users', '客户池'],
  ['clipboard', '背调队列'],
  ['mail', '开发信审核'],
  ['settings', '规则配置'],
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
  }
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function Status({ status }) {
  const labels = { evidence: ['证据充分', 'green'], complete: ['待补充', 'amber'], researching: ['研究中', 'blue'], review: ['待审核', 'orange'] }
  const [label, tone] = labels[status] || ['状态未知', 'amber']
  return <span className={`status status-${tone}`}><i />{label}</span>
}

function App() {
  const [selected, setSelected] = useState(null)
  const [remoteLeads, setRemoteLeads] = useState([])
  const [remoteTasks, setRemoteTasks] = useState([])
  const [remoteTaskId, setRemoteTaskId] = useState('')
  const [remoteTaskConfig, setRemoteTaskConfig] = useState(null)
  const [researchRuns, setResearchRuns] = useState([])
  const [researchLoading, setResearchLoading] = useState(false)
  const [mailboxStatus, setMailboxStatus] = useState(null)
  const [mailThreads, setMailThreads] = useState([])
  const [replyAnalyses, setReplyAnalyses] = useState([])
  const [followUpTasks, setFollowUpTasks] = useState([])
  const [replyLoading, setReplyLoading] = useState(false)
  const [selectedResearch, setSelectedResearch] = useState(null)
  const [selectedDraft, setSelectedDraft] = useState(null)
  const [selectedLeadAudit, setSelectedLeadAudit] = useState([])
  const [leadTransitionLoading, setLeadTransitionLoading] = useState(false)
  const [translatedDraft, setTranslatedDraft] = useState(null)
  const [translationLoading, setTranslationLoading] = useState(false)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [apiState, setApiState] = useState('loading')
  const [query, setQuery] = useState('')
  const [activeNav, setActiveNav] = useState('客户池')
  const [detailTab, setDetailTab] = useState('概览')
  const [language, setLanguage] = useState('中文')
  const [draftStatus, setDraftStatus] = useState('pending')
  const [showTask, setShowTask] = useState(false)
  const [toast, setToast] = useState('')
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
          setSelected(loaded[0] || null)
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
    Promise.all([
      fetch('/api/mailbox/status'),
      fetch(`/api/tasks/${remoteTaskId}/mail-threads`),
      fetch(`/api/tasks/${remoteTaskId}/reply-analyses`),
      fetch(`/api/tasks/${remoteTaskId}/follow-up-tasks`),
    ]).then(async ([statusResponse, threadsResponse, analysesResponse, followUpResponse]) => {
      if (!statusResponse.ok || !threadsResponse.ok || !analysesResponse.ok || !followUpResponse.ok) throw new Error('mail data failed')
      return Promise.all([statusResponse.json(), threadsResponse.json(), analysesResponse.json(), followUpResponse.json()])
    }).then(([status, threads, analyses, followUps]) => {
      if (!cancelled) { setMailboxStatus(status); setMailThreads(threads.items || []); setReplyAnalyses(analyses.items || []); setFollowUpTasks(followUps.items || []) }
    }).catch(() => { if (!cancelled) { setMailboxStatus(null); setMailThreads([]); setReplyAnalyses([]); setFollowUpTasks([]) } })
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
          if (runs.some((run) => run.status === 'running')) timer = window.setTimeout(loadRuns, 1200)
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
      .then(([data, audit]) => { if (!cancelled) { setSelectedResearch(data.research || null); setSelectedDraft(data.draft || null); setSelectedLeadAudit(audit.items || []); setTranslatedDraft(null) } })
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
  const displayLeads = remoteLeads
  const filteredLeads = useMemo(() => displayLeads.filter((lead) => `${lead.name} ${lead.country} ${lead.type}`.toLowerCase().includes(query.toLowerCase())), [displayLeads, query])
  const activeLead = selected ? { ...selected, type: selectedResearch ? customerTypeLabel(selectedResearch.customer_type) : selected.type, detail: selectedResearch?.business_summary || selected.detail, research: selectedResearch, draft: selectedDraft, auditEvents: selectedLeadAudit, researchRun: researchRuns.find((run) => run.domain === selected.domain), isRemote: true } : null

  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600) }
  const selectLead = (lead) => { setSelected(lead); setDetailTab('概览'); setDraftStatus('pending'); setTranslatedDraft(null) }
  const selectTask = (event) => {
    const task = remoteTasks.find((item) => item.id === event.target.value)
    if (!task) return
    setRemoteTaskId(task.id)
    setRemoteTaskConfig(task)
    setRemoteLeads([])
    setResearchRuns([])
    setMailThreads([])
    setReplyAnalyses([])
    setFollowUpTasks([])
    setApiState('loading')
    setSelected(null)
    setSelectedResearch(null)
    setSelectedDraft(null)
    setTranslatedDraft(null)
    setDetailTab('概览')
  }
  const translateDraft = async () => {
    if (!selectedDraft?.id) return
    setTranslationLoading(true)
    try {
      const response = await fetch(`/api/drafts/${selectedDraft.id}/translate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ target_language: 'zh-CN' }) })
      if (!response.ok) throw new Error('translation failed')
      setTranslatedDraft(await response.json())
      setLanguage('中文')
      notify('中文预览已生成，不会修改原始英文草稿')
    } catch { notify('翻译失败，请检查本地翻译服务或网络') } finally { setTranslationLoading(false) }
  }
  const reviewDraft = async (action, note, reviewer) => {
    if (!selectedDraft?.id || !reviewer.trim()) { notify('请先填写审核人'); return }
    if ((action === 'request-revision' || action === 'reject') && !note.trim()) { notify('请填写处理意见'); return }
    setReviewLoading(true)
    try {
      const response = await fetch(`/api/drafts/${selectedDraft.id}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reviewer: reviewer.trim(), note: note.trim() }) })
      if (!response.ok) throw new Error('review failed')
      setSelectedDraft(await response.json())
      notify(action === 'approve' ? '草稿已批准，尚未发送' : action === 'request-revision' ? '草稿已退回修改' : '草稿已拒绝')
    } catch { notify('审核操作失败，请检查本地 API') } finally { setReviewLoading(false) }
  }
  const generateDraft = async (template, product) => {
    if (!remoteTaskId || !selected?.domain) return
    setReviewLoading(true)
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/leads/${selected.domain}/draft`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ template, product }) })
      if (!response.ok) throw new Error('draft generation failed')
      setSelectedDraft(await response.json())
      setTranslatedDraft(null)
      notify('真实开发信草稿已生成，请人工审核')
    } catch { notify('开发信生成失败，请确认已完成背调并配置 DeepSeek') } finally { setReviewLoading(false) }
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
      notify('联系人已按来源证据更新，可继续生成开发信')
    } catch { notify('联系人更新失败，请检查邮箱格式和来源证据') }
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
      notify('客户状态已更新，审计记录已保存')
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
      notify(response.status === 202 ? '背调任务已进入队列，页面会自动刷新进度' : '背调已完成')
    } catch (error) { notify(error.message || '背调任务启动失败') } finally { setResearchLoading(false) }
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
  const updateFollowUpStatus = async (followUpId, status) => {
    if (!remoteTaskId) return
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/follow-up-tasks/${followUpId}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'follow-up update failed')
      setFollowUpTasks((items) => items.map((item) => item.id === followUpId ? payload.item : item))
      notify('跟进待办状态已更新')
    } catch (error) { notify(error.message || '跟进待办更新失败') }
  }
  const saveSenderProfile = async (profile) => {
    if (!remoteTaskId) return
    try {
      const response = await fetch(`/api/tasks/${remoteTaskId}/sender-profile`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(profile) })
      if (!response.ok) throw new Error('sender profile update failed')
      setRemoteTaskConfig(await response.json())
      notify('发件人资料已保存，重新生成时会创建新草稿版本')
    } catch { notify('发件人资料保存失败，请检查本地 API') }
  }
  const createTask = async (event) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload = {
      name: form.get('name'),
      criteria: {
        product: form.get('product'),
        countries: [form.get('country')],
        customer_types: [form.get('customerType')],
        daily_limit: 10,
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
      setSelected(null)
      setApiState('loading')
      setShowTask(false)
      notify('任务草稿已保存，已切换到当前任务')
    } catch {
      notify('任务保存失败，请检查本地 API')
    }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">✦</span><span>NORTHSTAR OPS</span></div>
      <nav>{navItems.map(([icon, label]) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => { setActiveNav(label); notify(`${label}模块将在下一阶段接入`) }}><Icon name={icon} /><span>{label}</span></button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-rule"/><p>让中国制造<br/>连接全球真实需求</p><small>NORTHSTAR OPS<br/><em>v0.1.0 · LOCAL</em></small></div>
    </aside>
    <main className="main-shell">
      <header className="topbar"><div className="search-global"><Icon name="search" size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索公司、域名或关键词…"/><kbd>⌘ K</kbd></div><div className="top-actions"><button className="icon-button" onClick={() => notify('暂无新的系统通知')} aria-label="通知"><Icon name="bell" size={20}/><i className="notification-dot"/></button><span className="top-divider"/><div className="profile"><span className="avatar">LO</span><span><strong>本地操作人</strong><small>当前工作区</small></span><span className="chevron">⌄</span></div></div></header>
      <div className="content">
        <div className="page-heading"><div><h1>客户智能工作台</h1><p>从公开证据到可审核的下一步</p></div><button className="primary-button" onClick={() => setShowTask(true)}><Icon name="plus" size={19}/>新建获客任务</button></div>
        <div className={`data-notice ${apiState}`}><span />{apiState === 'loading' ? '正在读取本地任务数据…' : apiState === 'connected' ? '已连接本地 API · 当前显示持久化客户档案' : apiState === 'empty' ? 'API 已连接 · 当前没有可显示的真实客户档案' : 'API 连接失败 · 为避免混淆，已隐藏演示数据'}</div>
        <div className="task-context"><label>当前获客任务<select value={remoteTaskId} onChange={selectTask} disabled={!remoteTasks.length}><option value="">暂无可选任务</option>{remoteTasks.map((task) => <option key={task.id} value={task.id}>{task.name}</option>)}</select></label>{remoteTaskConfig && <span>任务条件：{remoteTaskConfig.criteria?.product || '未配置产品'} · {remoteTaskConfig.criteria?.countries?.join('、') || '未配置市场'}</span>}</div>
        <section className="metric-row"><Metric icon="clipboard" label="待审核" value="—" note="统计接口尚未接入"/><Metric icon="users" label="高匹配客户" value="—" note="统计接口尚未接入"/><Metric icon="researching" label="本周新增" value="—" note="统计接口尚未接入"/></section>
        <ReplyCenter mailboxStatus={mailboxStatus} threads={mailThreads} analyses={replyAnalyses} followUpTasks={followUpTasks} loading={replyLoading} onTest={testMailbox} onSync={syncMailbox} onAnalyze={analyzeReplies} onFollowUpStatus={updateFollowUpStatus}/>
        <section className="workspace-grid">
          <div className="lead-panel panel"><div className="panel-heading"><div><h2>客户列表 <span>共 {filteredLeads.length} 个</span></h2><p>已按当前任务条件筛选</p></div><button className="filter-button" onClick={() => notify('筛选条件：国家、类型、评分、状态')}><Icon name="filter" size={16}/>筛选</button></div><div className="table-head"><span className="checkbox"/><span>公司名称</span><span>国家 / 地区</span><span>客户类型</span><span>匹配分数</span><span>状态</span><span/></div><div className="lead-list">{filteredLeads.length ? filteredLeads.map((lead) => <button className={`lead-row ${selected?.name === lead.name ? 'selected' : ''}`} key={lead.name} onClick={() => selectLead(lead)}><span className={`checkbox ${selected?.name === lead.name ? 'checked' : ''}`}>{selected?.name === lead.name && <Icon name="check" size={13}/>}</span><strong>{lead.name}</strong><span className="country"><span>{lead.flag}</span>{lead.country}</span><span>{lead.type}</span><span className="score"><b>{lead.score}</b> / 100</span><Status status={lead.status}/><span className="more">···</span></button>) : <div className="empty-results">没有匹配的客户，请调整搜索词</div>}</div><div className="table-footer"><span>当前筛选 {filteredLeads.length} 条</span><div className="pagination"><button>‹</button><button className="page-active">1</button><button>2</button><button>3</button><button>4</button><span>…</span><button>13</button><button>›</button></div></div></div>
          <aside className={`detail-panel panel ${filteredLeads.length && activeLead ? '' : 'detail-empty'}`}>{filteredLeads.length && activeLead ? <><div className="detail-top"><div className="company-symbol">◎</div><div className="company-title"><div><h2>{activeLead.name} <a href={activeLead.website} target="_blank" rel="noreferrer"><Icon name="external" size={14}/></a></h2><p>{activeLead.country} <i/> {activeLead.type} <i/> {activeLead.research ? '已完成官网背调' : '待背调'}</p></div><div className="score-block"><Status status={activeLead.status}/><strong>{activeLead.score}<small> / 100</small></strong><span>匹配分数</span></div></div></div><div className="detail-tabs">{['概览', '来源证据', '开发信草稿'].map((tab) => <button className={detailTab === tab ? 'active' : ''} key={tab} onClick={() => setDetailTab(tab)}>{tab}</button>)}</div>{detailTab === '概览' && <><Overview lead={activeLead} onEvidence={() => setDetailTab('来源证据')} onDraft={() => setDetailTab('开发信草稿')}/><ResearchPanel lead={activeLead} loading={researchLoading} onStart={startResearch}/><LeadTimeline lead={activeLead} events={activeLead.auditEvents} onTransition={transitionLead} loading={leadTransitionLoading}/></>} {detailTab === '来源证据' && <Evidence lead={activeLead}/>} {detailTab === '开发信草稿' && <><Draft lead={activeLead} language={language} setLanguage={setLanguage} translatedDraft={translatedDraft} translationLoading={translationLoading} onTranslate={translateDraft} onReview={reviewDraft} reviewLoading={reviewLoading} status={draftStatus} setStatus={setDraftStatus} notify={notify}/><ContactForm lead={activeLead} onUpdate={updateContact}/><SenderProfileEditor taskConfig={remoteTaskConfig} onSave={saveSenderProfile}/><DraftGenerator lead={activeLead} taskConfig={remoteTaskConfig} loading={reviewLoading} onGenerate={generateDraft}/><ReviewControls lead={activeLead} onReview={reviewDraft} loading={reviewLoading}/></>}</> : <div className="detail-empty-state"><strong>没有选中的客户</strong><span>调整搜索词后选择一条客户记录</span></div>}</aside>
        </section>
      </div>
    </main>
    {toast && <div className="toast"><span>✓</span>{toast}</div>}
    {showTask && <div className="modal-backdrop" onClick={() => setShowTask(false)}><form className="task-modal" onSubmit={createTask} onClick={(event) => event.stopPropagation()}><button type="button" className="modal-close" onClick={() => setShowTask(false)}>×</button><span className="modal-icon"><Icon name="plus"/></span><h2>新建获客任务</h2><p>定义目标产品、国家、客户类型和发件人资料，系统将按规则运行搜索与背调。</p><label>任务名称<input name="name" defaultValue="便携式太阳能发电机 · 欧洲渠道" required/></label><label>目标产品<input name="product" defaultValue="portable solar generator" required/></label><div className="modal-grid"><label>目标市场<select name="country" defaultValue="Germany"><option>Germany</option><option>France</option><option>Netherlands</option></select></label><label>客户类型<select name="customerType" defaultValue="Distributor"><option value="distributor">Distributor</option><option value="retailer">Retailer</option><option value="wholesaler">Wholesaler</option></select></label></div><div className="sender-config"><strong>发件人资料（可选）</strong><p>填写后用于生成新开发信；留空则继续使用占位符。</p><label>公司名称<input name="senderCompany" placeholder="例如：ABC Trading Co., Ltd." /></label><label>联系人姓名<input name="senderName" placeholder="例如：Li Ming" /></label><label>职位<input name="senderPosition" placeholder="例如：Sales Manager" /></label></div><button type="submit" className="primary-button full">创建任务草稿 <Icon name="arrow" size={16}/></button></form></div>}
  </div>
}

function mapRemoteLead(item) {
  const lead = item.lead
  return {
    name: lead.company_name,
    country: lead.country || 'Unknown',
    flag: '·',
    type: 'Unknown',
    score: item.score?.total || 0,
    status: lead.quality === 'complete' ? 'evidence' : 'review',
    workflowStatus: lead.status || 'new',
    detail: '已从本地持久化客户档案读取，等待更多背调字段接入。',
    email: lead.emails?.[0] || '未发现公开邮箱',
    website: lead.website || `https://${lead.domain}`,
    domain: lead.domain,
    isRemote: true,
  }
}

function customerTypeLabel(value) {
  return { retailer: 'Retailer', distributor: 'Distributor', wholesaler: 'Wholesaler', manufacturer: 'Manufacturer', consumer: 'Consumer', service_provider: 'Service provider', unknown: '未知' }[value] || '未知'
}

function Metric({ icon, label, value, note }) { return <div className="metric"><span className={`metric-icon ${icon}`}><Icon name={icon === 'researching' ? 'users' : icon} size={20}/></span><div><span>{label}</span><strong>{value}<Icon name="arrow" size={16}/></strong><small>{note}</small></div></div> }
function ReplyCenter({ mailboxStatus, threads, analyses, followUpTasks, loading, onTest, onSync, onAnalyze, onFollowUpStatus }) {
  const humanReview = analyses.filter((item) => item.needs_human_review).length
  const analyzableThreads = threads.filter((thread) => !thread.is_system_notification)
 return <section className="reply-center panel"><div className="reply-center-heading"><div><h2>收件与回复分析 <span>{threads.length} 封来信 · {analyses.length} 条分析</span></h2><p>{mailboxStatus?.configured ? '阿里邮箱 IMAP 已配置 · 只读模式' : '阿里邮箱尚未配置 · 不会连接或发送邮件'}</p></div><div className="reply-actions"><button className="outline-button" disabled={loading || !mailboxStatus?.configured} onClick={onTest}>测试只读连接</button><button className="outline-button" disabled={loading || !mailboxStatus?.configured} onClick={onSync}>同步收件箱</button><button className="primary-button" disabled={loading || !analyzableThreads.length} onClick={onAnalyze}>{loading ? '处理中…' : '分析已同步来信'}</button></div></div>{threads.length ? <><div className="reply-summary"><span>人工复核 {humanReview} 条</span>{analyses.length ? <span>已生成安全建议</span> : <span>尚未分析</span>}<span>待办 {followUpTasks.length} 条</span></div><div className="reply-list">{threads.map((thread) => { const analysis = analyses.find((item) => item.message_id === thread.message_id); const followUp = followUpTasks.find((item) => item.message_id === thread.message_id); return <article className="reply-item" key={thread.message_id}><div><strong>{thread.from_email || '未知发件人'}</strong><span>{thread.subject || '无主题'}{thread.is_bounce ? ' · 退信' : ''}{thread.is_system_notification ? ' · 系统通知' : ''}</span></div>{analysis ? <div className="reply-analysis"><b>{replyCategoryLabel(analysis.category)}</b><span>{(analysis.confidence * 100).toFixed(0)}% · {analysis.risk_level === 'high' ? '高风险' : analysis.risk_level === 'medium' ? '中风险' : '低风险'}</span><p>{analysis.suggested_action}{analysis.needs_human_review ? ' · 需要人工复核' : ''}</p>{followUp && <label className="follow-up-status">跟进待办：<select value={followUp.status} onChange={(event) => onFollowUpStatus(followUp.id, event.target.value)}><option value="open">待处理</option><option value="in_progress">处理中</option><option value="completed">已完成</option><option value="cancelled">已取消</option></select></label>}</div> : <em>{thread.is_system_notification ? '系统通知 · 不进入客户回复分析' : '尚未分析'}</em>}</article> })}</div></> : <div className="reply-empty"><strong>当前没有真实来信</strong><span>配置专用测试邮箱并完成只读同步后，这里才会显示邮件与分类建议。</span></div>}</section>
}

function replyCategoryLabel(category) { return { interested: '有意向', pricing: '询价', delivery: '交期/物流', complaint: '投诉', bounce: '退信', not_interested: '暂不考虑', other: '其他' }[category] || category }
function ResearchPanel({ lead, loading, onStart }) {
  const [sourceUrl, setSourceUrl] = useState(lead.website || '')
  const [maxAttempts, setMaxAttempts] = useState('2')
  const [requestKey, setRequestKey] = useState('')
  const run = lead.researchRun
  const running = run?.status === 'running'
  return <div className="review-controls research-panel"><div className="section-title"><h3>官网背调队列</h3><span>{run ? `${researchStepLabel(run.step)} · ${run.attempts} 次尝试` : '尚未提交'}</span></div><label>来源网址<input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></label><div className="research-fields"><label>最大尝试次数<select value={maxAttempts} onChange={(event) => setMaxAttempts(event.target.value)}><option value="1">1 次</option><option value="2">2 次</option><option value="3">3 次</option></select></label><label>幂等键（可选）<input value={requestKey} onChange={(event) => setRequestKey(event.target.value)} placeholder="同一请求复用" /></label></div><button className="primary-button full" disabled={loading || running || !sourceUrl.trim()} onClick={() => onStart(sourceUrl.trim(), Number(maxAttempts), requestKey.trim())}>{loading ? '提交中…' : running ? '队列执行中…' : run?.status === 'failed' ? '重新提交背调' : '加入背调队列'} <Icon name="arrow" size={16}/></button>{run?.error && <p className="generator-hint">失败原因：{run.error}</p>}{['succeeded', 'review_required'].includes(run?.status) && <p className="research-success">运行已完成，研究报告已自动刷新。</p>}</div>
}

function researchStepLabel(step) { return { queued: '排队中', fetching: '抓取官网', analyzing: '分析内容', scoring: '计算评分', persisting: '保存报告', completed: '已完成', failed: '失败' }[step] || step }
function Overview({ lead, onEvidence, onDraft }) { const research = lead.research; const products = research?.products?.join('、') || '未知'; return <div className="detail-body"><h3>公司概览</h3><dl><dt>官网</dt><dd><a href={lead.website} target="_blank" rel="noreferrer">{lead.website.replace('https://', '').replace(/\/$/, '')}<Icon name="external" size={13}/></a></dd><dt>行业</dt><dd>未从当前证据确认</dd><dt>公司规模</dt><dd>未知</dd><dt>主要市场</dt><dd>{research?.country || lead.country || '未知'}</dd><dt>产品</dt><dd>{products}</dd><dt>简介</dt><dd>{lead.detail || '未知'}</dd></dl><div className="section-divider"/><div className="section-title"><h3>来源证据</h3><button className="outline-button" onClick={onEvidence}>查看来源 <Icon name="arrow" size={14}/></button></div><div className="evidence-mini"><span className="evidence-icon"><Icon name="clipboard" size={15}/></span><div><strong>官网背调来源</strong><p>{research?.evidence_url || '尚未保存来源'}</p></div><time>{research ? `置信度 ${(research.confidence * 100).toFixed(0)}%` : '未知日期'}</time></div><div className="section-divider"/><div className="section-title"><h3>开发信草稿</h3><button className="text-button" onClick={onDraft}>查看详情 <Icon name="arrow" size={14}/></button></div><div className="draft-snippet"><span className="draft-status-dot"/><div><strong>{lead.isRemote ? '尚未生成' : '待人工审核'}</strong><p>{lead.isRemote ? '真实开发信服务尚未接入' : '等待人工审核'}</p></div><Icon name="arrow" size={16}/></div></div> }
function Evidence({ lead }) { const research = lead.research; return <div className="detail-body evidence-view"><div className="section-title"><h3>来源证据</h3><span className="evidence-count">{research ? '已保存 1 条' : '未知'}</span></div><p className="evidence-intro">以下内容来自公开页面，AI 结论只能作为建议，必须回到原始来源复核。</p><div className="timeline"><div className="timeline-item"><span className="timeline-dot"><Icon name="clipboard" size={13}/></span><div><time>{research ? `置信度 ${(research.confidence * 100).toFixed(0)}%` : '未知时间'}</time><strong>官网背调来源</strong><p>{research?.business_summary || '尚未保存背调摘要。'}</p>{research?.evidence_url && <a href={research.evidence_url} target="_blank" rel="noreferrer">打开来源 <Icon name="external" size={12}/></a>}</div></div></div></div> }
function Draft({ lead, language, setLanguage, translatedDraft, translationLoading, onTranslate, status, setStatus, notify }) { const draft = lead.draft; const isDraftAvailable = Boolean(draft) || !lead.isRemote; const useTranslation = Boolean(draft && language === '中文' && translatedDraft); const body = useTranslation ? translatedDraft.body : draft?.body || (!isDraftAvailable ? '真实开发信尚未生成，当前不会发送任何邮件。' : language === '中文' ? `您好，${lead.name} 团队：\n\n我们是一家专注于便携式太阳能发电机及相关配件的中国制造商。了解到贵司在德国市场提供太阳能产品，我们想与您探讨产品目录是否有互补的机会。\n\n如果方向合适，我可以发送产品资料供您参考。` : `Hello ${lead.name} team,\n\nWe are a Chinese manufacturer focused on portable solar generators and related accessories. We noticed that your company offers solar products in Germany and would like to explore whether our product range could complement your current offering.\n\nIf relevant, I would be happy to share our product catalogue for your review.`); const recipient = draft?.recipient_email || (lead.email && lead.email.includes('@') ? lead.email : '未发现公开邮箱'); const subject = useTranslation ? translatedDraft.subject : draft?.subject || (isDraftAvailable ? (language === '中文' ? '关于便携式太阳能产品合作' : 'Portable solar products for your range') : '尚未生成'); const canApprove = Boolean(draft) && recipient.includes('@') && draft.status !== 'approved'; const currentStatus = draft?.status === 'approved' ? 'approved' : draft?.status === 'revision_required' ? 'revision' : status; return <div className="detail-body draft-view"><div className="section-title"><h3>开发信草稿</h3>{draft ? <div className="language-toggle"><button className={language === 'EN' ? 'active' : ''} onClick={() => setLanguage('EN')}>EN</button><button className={language === '中文' ? 'active' : ''} onClick={() => { setLanguage('中文'); if (!translatedDraft) onTranslate() }}>{translationLoading ? '翻译中…' : '中文预览'}</button></div> : isDraftAvailable && <div className="language-toggle">{['中文', 'EN'].map((item) => <button key={item} className={language === item ? 'active' : ''} onClick={() => setLanguage(item)}>{item}</button>)}</div>}</div><div className="review-banner"><span className="review-pulse"/><div><strong>{draft ? (currentStatus === 'approved' ? '已批准' : currentStatus === 'revision' ? '需修改' : '待人工审核') : '尚未生成'}</strong><p>{draft ? (useTranslation ? '中文仅用于阅读预览，原始英文草稿未修改' : '发送前必须由人工确认收件人与正文') : '真实 DeepSeek 开发信服务尚未接入'}</p></div></div><div className="email-preview"><div className="email-meta"><span>收件人</span><strong>{recipient}</strong></div><div className="email-meta"><span>主题</span><strong>{subject}</strong></div><div className="email-copy">{body.split('\n').map((line, index) => <p key={`${line}-${index}`}>{line || '\u00a0'}</p>)}</div><div className="evidence-tag"><Icon name="clipboard" size={13}/>{draft ? `内容基于 ${draft.evidence_urls?.length || 0} 条真实背调证据` : '当前没有真实开发信内容'}</div></div><div className="draft-actions"><button className="more-button" disabled={!draft} onClick={() => notify('更多操作将在后续阶段接入')}>···</button><button className="outline-button" disabled={!draft} onClick={() => { setStatus('revision'); notify('请通过审核接口提交修改意见') }}>退回修改</button><button className="primary-button" disabled={!canApprove} onClick={() => notify('审核接口将在下一步接入前端')}><Icon name="check" size={16}/>{currentStatus === 'approved' ? '已批准' : '批准草稿'}</button></div></div> }

function ContactForm({ lead, onUpdate }) {
  const [email, setEmail] = useState('')
  const [sourceUrl, setSourceUrl] = useState(lead.website || '')
  const [sourceExcerpt, setSourceExcerpt] = useState('')
  if (!lead.isRemote || lead.draft || lead.email?.includes('@')) return null
  return <div className="review-controls contact-form"><div className="section-title"><h3>补充公开联系人</h3><span>必须保留来源证据</span></div><label>公开邮箱<input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="例如：sales@example.com" /></label><label>来源网址<input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="公开页面 URL" /></label><label>来源说明<textarea value={sourceExcerpt} onChange={(event) => setSourceExcerpt(event.target.value)} placeholder="例如：官网 Contact 页面展示该邮箱" rows="2" /></label><button className="outline-button full" disabled={!email.trim() || !sourceUrl.trim() || !sourceExcerpt.trim()} onClick={() => onUpdate(email, sourceUrl, sourceExcerpt)}>保存联系人证据</button></div>
}

function SenderProfileEditor({ taskConfig, onSave }) {
  const profile = taskConfig?.sender_profile || {}
  const [companyName, setCompanyName] = useState(profile.company_name || '')
  const [contactName, setContactName] = useState(profile.contact_name || '')
  const [position, setPosition] = useState(profile.position || '')
  return <div className="review-controls sender-editor"><div className="section-title"><h3>发件人资料</h3><span>用于下一版草稿</span></div><label>公司名称<input value={companyName} onChange={(event) => setCompanyName(event.target.value)} placeholder="例如：ABC Trading Co., Ltd." /></label><label>联系人姓名<input value={contactName} onChange={(event) => setContactName(event.target.value)} placeholder="例如：Li Ming" /></label><label>职位<input value={position} onChange={(event) => setPosition(event.target.value)} placeholder="例如：Sales Manager" /></label><button className="outline-button full" onClick={() => onSave({ company_name: companyName, contact_name: contactName, position })}>保存发件人资料</button></div>
}

function DraftGenerator({ lead, taskConfig, loading, onGenerate }) {
  const [product, setProduct] = useState(taskConfig?.criteria?.product || '')
  const [template, setTemplate] = useState('Introduce {product} to {company} based on their published product range.')
  if (!lead.isRemote) return null
  const hasRecipient = Boolean(lead.email?.includes('@'))
  return <div className="review-controls draft-generator"><div className="section-title"><h3>{lead.draft ? '重新生成开发信' : '生成开发信'}</h3><span>{lead.draft ? '会创建新版本，不覆盖当前草稿' : '使用真实背调与已配置发件人资料'}</span></div><label>产品或服务<input value={product} onChange={(event) => setProduct(event.target.value)} placeholder="填写本次推广产品" /></label><label>写作方向<textarea value={template} onChange={(event) => setTemplate(event.target.value)} rows="2" /></label><button className="primary-button full" disabled={loading || !product.trim() || !lead.research || !hasRecipient} onClick={() => onGenerate(template, product)}>{loading ? '生成中…' : lead.draft ? '生成新版本草稿' : '生成真实开发信草稿'} <Icon name="arrow" size={16}/></button>{!hasRecipient ? <p className="generator-hint">当前没有公开邮箱，补充真实收件人后才能生成。</p> : !lead.research && <p className="generator-hint">请先完成官网背调，再生成开发信。</p>}</div>
}

function ReviewControls({ lead, onReview, loading }) {
  const [reviewer, setReviewer] = useState('')
  const [note, setNote] = useState('')
  if (!lead.draft) return null
  const locked = loading || lead.draft.status === 'approved' || lead.draft.status === 'rejected'
  return <div className="review-controls"><div className="section-title"><h3>审核操作</h3><span>仅改变审核状态，不发送邮件</span></div><label>审核人<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="填写姓名" /></label><label>处理意见<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="退回或拒绝时必填" rows="2" /></label><div className="review-control-actions"><button className="outline-button" disabled={locked || !reviewer.trim() || !note.trim()} onClick={() => onReview('request-revision', note, reviewer)}>{loading ? '处理中…' : '退回修改'}</button><button className="primary-button" disabled={locked || !reviewer.trim()} onClick={() => onReview('approve', note, reviewer)}>批准草稿</button></div></div>
}

export default App
function LeadTimeline({ lead, events, onTransition, loading }) {
  const [target, setTarget] = useState('awaiting_score')
  const [actor, setActor] = useState('')
  const [note, setNote] = useState('')
  return <div className="lead-timeline"><div className="section-title"><h3>状态时间线</h3><span>当前：{lead.workflowStatus || 'new'} · {events.length} 条记录</span></div><div className="lead-transition"><select value={target} onChange={(event) => setTarget(event.target.value)}><option value="awaiting_score">待评分</option><option value="awaiting_review">待审核</option><option value="selected">已入选</option><option value="contacted">已联系</option><option value="replied">已回复</option><option value="following_up">跟进中</option><option value="paused">暂缓</option><option value="invalid">无效</option></select><input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="操作人"/><input value={note} onChange={(event) => setNote(event.target.value)} placeholder="变更原因（可选）"/><button className="outline-button" disabled={loading || !actor.trim() || target === lead.workflowStatus} onClick={() => onTransition(target, actor, note)}>{loading ? '保存中…' : target === lead.workflowStatus ? '已是当前状态' : '更新状态'}</button></div>{events.length ? <div className="timeline-list">{events.map((event) => <div className="timeline-row" key={event.id}><strong>{event.from_status} → {event.to_status}</strong><span>{event.actor} · {new Date(event.occurred_at).toLocaleString()}</span>{event.note && <p>{event.note}</p>}</div>)}</div> : <p className="timeline-empty">客户状态尚未发生可审计变更。</p>}</div>
}
