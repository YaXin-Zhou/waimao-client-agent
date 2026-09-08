import { useMemo, useState } from 'react'

const leads = [
  { name: 'Solar-Generatoren.de', country: 'Germany', flag: '🇩🇪', type: 'Retailer', score: 25, status: 'evidence', detail: '专注于便携式太阳能发电机及户外能源解决方案的在线零售商。', email: 'Kontakt (AT) Solar-Generatoren.de', website: 'https://solar-generatoren.de/' },
  { name: 'GreenPower Solutions', country: 'France', flag: '🇫🇷', type: 'Distributor', score: 18, status: 'complete', detail: '面向欧洲市场提供便携储能与户外电源产品的分销商。', email: 'sales@greenpower.example', website: 'https://greenpower.example/' },
  { name: 'SunVolt GmbH', country: 'Germany', flag: '🇩🇪', type: 'Wholesaler', score: 22, status: 'researching', detail: '批发太阳能组件与小型储能设备，正在补充联系人信息。', email: 'info@sunvolt.example', website: 'https://sunvolt.example/' },
  { name: 'EcoTech Retail', country: 'Netherlands', flag: '🇳🇱', type: 'Retailer', score: 17, status: 'review', detail: '线上零售环保能源设备，产品类别与目标产品部分重合。', email: 'hello@ecotech.example', website: 'https://ecotech.example/' },
  { name: 'PowerHome SAS', country: 'France', flag: '🇫🇷', type: 'Retailer', score: 20, status: 'complete', detail: '家用应急电源及户外能源产品零售商。', email: 'contact@powerhome.example', website: 'https://powerhome.example/' },
  { name: 'Solar & More', country: 'Belgium', flag: '🇧🇪', type: 'Distributor', score: 19, status: 'researching', detail: '比利时太阳能及储能产品渠道服务商。', email: 'sales@solar-more.example', website: 'https://solar-more.example/' },
  { name: 'Renewable Goods Ltd', country: 'United Kingdom', flag: '🇬🇧', type: 'Retailer', score: 16, status: 'review', detail: '可再生能源消费品零售渠道。', email: 'team@renewable-goods.example', website: 'https://renewable-goods.example/' },
  { name: 'SunLife Store', country: 'Spain', flag: '🇪🇸', type: 'Retailer', score: 18, status: 'complete', detail: '西班牙户外及露营能源装备零售商。', email: 'ventas@sunlife.example', website: 'https://sunlife.example/' },
]

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
  const [label, tone] = labels[status]
  return <span className={`status status-${tone}`}><i />{label}</span>
}

function App() {
  const [selected, setSelected] = useState(leads[0])
  const [query, setQuery] = useState('')
  const [activeNav, setActiveNav] = useState('客户池')
  const [detailTab, setDetailTab] = useState('概览')
  const [language, setLanguage] = useState('中文')
  const [draftStatus, setDraftStatus] = useState('pending')
  const [showTask, setShowTask] = useState(false)
  const [toast, setToast] = useState('')
  const filteredLeads = useMemo(() => leads.filter((lead) => `${lead.name} ${lead.country} ${lead.type}`.toLowerCase().includes(query.toLowerCase())), [query])

  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2600) }
  const selectLead = (lead) => { setSelected(lead); setDetailTab('概览'); setDraftStatus('pending') }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">✦</span><span>NORTHSTAR OPS</span></div>
      <nav>{navItems.map(([icon, label]) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => { setActiveNav(label); notify(`${label}模块将在下一阶段接入`) }}><Icon name={icon} /><span>{label}</span>{label === '开发信审核' && <b>12</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-rule"/><p>让中国制造<br/>连接全球真实需求</p><small>NORTHSTAR OPS<br/><em>v0.1.0 · LOCAL</em></small></div>
    </aside>
    <main className="main-shell">
      <header className="topbar"><div className="search-global"><Icon name="search" size={17}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索公司、域名或关键词…"/><kbd>⌘ K</kbd></div><div className="top-actions"><button className="icon-button" onClick={() => notify('暂无新的系统通知')} aria-label="通知"><Icon name="bell" size={20}/><i className="notification-dot"/></button><span className="top-divider"/><div className="profile"><span className="avatar">ZL</span><span><strong>张力</strong><small>销售团队</small></span><span className="chevron">⌄</span></div></div></header>
      <div className="content">
        <div className="page-heading"><div><h1>客户智能工作台</h1><p>从公开证据到可审核的下一步</p></div><button className="primary-button" onClick={() => setShowTask(true)}><Icon name="plus" size={19}/>新建获客任务</button></div>
        <section className="metric-row"><Metric icon="clipboard" label="待审核" value="12" note="需要你的判断"/><Metric icon="users" label="高匹配客户" value="28" note="本周 +6"/><Metric icon="researching" label="本周新增" value="37" note="来自 4 个市场"/></section>
        <section className="workspace-grid">
          <div className="lead-panel panel"><div className="panel-heading"><div><h2>客户列表 <span>共 {filteredLeads.length || 128} 个</span></h2><p>已按当前任务条件筛选</p></div><button className="filter-button" onClick={() => notify('筛选条件：国家、类型、评分、状态')}><Icon name="filter" size={16}/>筛选</button></div><div className="table-head"><span className="checkbox"/><span>公司名称</span><span>国家 / 地区</span><span>客户类型</span><span>匹配分数</span><span>状态</span><span/></div><div className="lead-list">{filteredLeads.map((lead) => <button className={`lead-row ${selected.name === lead.name ? 'selected' : ''}`} key={lead.name} onClick={() => selectLead(lead)}><span className={`checkbox ${selected.name === lead.name ? 'checked' : ''}`}>{selected.name === lead.name && <Icon name="check" size={13}/>}</span><strong>{lead.name}</strong><span className="country"><span>{lead.flag}</span>{lead.country}</span><span>{lead.type}</span><span className="score"><b>{lead.score}</b> / 100</span><Status status={lead.status}/><span className="more">···</span></button>)}</div><div className="table-footer"><span>每页 10 条，共 128 条</span><div className="pagination"><button>‹</button><button className="page-active">1</button><button>2</button><button>3</button><button>4</button><span>…</span><button>13</button><button>›</button></div></div></div>
          <aside className="detail-panel panel"><div className="detail-top"><div className="company-symbol">◎</div><div className="company-title"><div><h2>{selected.name} <a href={selected.website} target="_blank" rel="noreferrer"><Icon name="external" size={14}/></a></h2><p>{selected.country} <i/> {selected.type} <i/> 成立信息待核验</p></div><div className="score-block"><Status status={selected.status}/><strong>{selected.score}<small> / 100</small></strong><span>匹配分数</span></div></div></div><div className="detail-tabs">{['概览', '来源证据', '开发信草稿'].map((tab) => <button className={detailTab === tab ? 'active' : ''} key={tab} onClick={() => setDetailTab(tab)}>{tab}</button>)}</div>{detailTab === '概览' && <Overview lead={selected} onEvidence={() => setDetailTab('来源证据')}/>} {detailTab === '来源证据' && <Evidence lead={selected}/>} {detailTab === '开发信草稿' && <Draft language={language} setLanguage={setLanguage} status={draftStatus} setStatus={setDraftStatus} notify={notify}/>}</aside>
        </section>
      </div>
    </main>
    {toast && <div className="toast"><span>✓</span>{toast}</div>}
    {showTask && <div className="modal-backdrop" onClick={() => setShowTask(false)}><div className="task-modal" onClick={(event) => event.stopPropagation()}><button className="modal-close" onClick={() => setShowTask(false)}>×</button><span className="modal-icon"><Icon name="plus"/></span><h2>新建获客任务</h2><p>定义目标产品、国家和客户类型，系统将按规则运行搜索与背调。</p><label>任务名称<input defaultValue="便携式太阳能发电机 · 欧洲渠道"/></label><label>目标产品<input defaultValue="portable solar generator"/></label><div className="modal-grid"><label>目标市场<select defaultValue="Germany"><option>Germany</option><option>France</option><option>Netherlands</option></select></label><label>客户类型<select defaultValue="Distributor"><option>Distributor</option><option>Retailer</option><option>Wholesaler</option></select></label></div><button className="primary-button full" onClick={() => { setShowTask(false); notify('任务草稿已创建，下一步将配置规则') }}>创建任务草稿 <Icon name="arrow" size={16}/></button></div></div>}
  </div>
}

function Metric({ icon, label, value, note }) { return <div className="metric"><span className={`metric-icon ${icon}`}><Icon name={icon === 'researching' ? 'users' : icon} size={20}/></span><div><span>{label}</span><strong>{value}<Icon name="arrow" size={16}/></strong><small>{note}</small></div></div> }
function Overview({ lead, onEvidence }) { return <div className="detail-body"><h3>公司概览</h3><dl><dt>官网</dt><dd><a href={lead.website} target="_blank" rel="noreferrer">{lead.website.replace('https://', '').replace(/\/$/, '')}<Icon name="external" size={13}/></a></dd><dt>行业</dt><dd>Consumer Electronics <i>›</i> Solar Products</dd><dt>公司规模</dt><dd>11–50 人（推测）</dd><dt>主要市场</dt><dd>{lead.country}, EU</dd><dt>简介</dt><dd>{lead.detail}</dd></dl><div className="section-divider"/><div className="section-title"><h3>来源证据</h3><button className="outline-button" onClick={onEvidence}>查看来源 <Icon name="arrow" size={14}/></button></div><div className="evidence-mini"><span className="evidence-icon"><Icon name="clipboard" size={15}/></span><div><strong>官网产品页面</strong><p>公开页面显示其销售便携式太阳能发电机、太阳能板及配件</p></div><time>2024-11-02</time></div><div className="evidence-mini"><span className="evidence-icon"><Icon name="users" size={15}/></span><div><strong>公司公开信息</strong><p>公司主体与公开联系方式已记录，邮箱未进行猜测</p></div><time>2024-11-02</time></div><div className="section-divider"/><div className="section-title"><h3>开发信草稿</h3><button className="text-button" onClick={() => onEvidence()}>查看详情 <Icon name="arrow" size={14}/></button></div><div className="draft-snippet"><span className="draft-status-dot"/><div><strong>待人工审核</strong><p>已根据背调事实生成中文草稿</p></div><Icon name="arrow" size={16}/></div></div> }
function Evidence({ lead }) { return <div className="detail-body evidence-view"><div className="section-title"><h3>来源证据</h3><span className="evidence-count">已核验 2 条</span></div><p className="evidence-intro">以下内容来自公开页面，所有 AI 结论均应回到原始来源复核。</p><div className="timeline"><div className="timeline-item"><span className="timeline-dot"><Icon name="clipboard" size={13}/></span><div><time>2024-11-02</time><strong>官网产品页面</strong><p>销售便携式太阳能发电机、太阳能板及配件。</p><a href={lead.website} target="_blank" rel="noreferrer">打开来源 <Icon name="external" size={12}/></a></div></div><div className="timeline-item"><span className="timeline-dot"><Icon name="users" size={13}/></span><div><time>2024-11-02</time><strong>公司公开信息</strong><p>{lead.name} 的公开主体与联系方式已纳入客户档案。</p><a href={lead.website} target="_blank" rel="noreferrer">打开来源 <Icon name="external" size={12}/></a></div></div></div></div> }
function Draft({ language, setLanguage, status, setStatus, notify }) { const body = language === '中文' ? '您好，Solar-Generatoren 团队：\n\n我们是一家专注于便携式太阳能发电机及相关配件的中国制造商。了解到贵司在德国市场提供太阳能产品，我们想与您探讨产品目录是否有互补的机会。\n\n如果方向合适，我可以发送产品资料供您参考。' : 'Hello Solar-Generatoren team,\n\nWe are a Chinese manufacturer focused on portable solar generators and related accessories. We noticed that your company offers solar products in Germany and would like to explore whether our product range could complement your current offering.\n\nIf relevant, I would be happy to share our product catalogue for your review.'; return <div className="detail-body draft-view"><div className="section-title"><h3>开发信草稿</h3><div className="language-toggle">{['中文', 'EN'].map((item) => <button key={item} className={language === item ? 'active' : ''} onClick={() => setLanguage(item)}>{item}</button>)}</div></div><div className="review-banner"><span className="review-pulse"/><div><strong>{status === 'approved' ? '已批准' : status === 'revision' ? '需修改' : '待人工审核'}</strong><p>{status === 'approved' ? '审核完成，尚未发送' : '发送前必须由人工确认收件人与正文'}</p></div></div><div className="email-preview"><div className="email-meta"><span>收件人</span><strong>Kontakt (AT) Solar-Generatoren.de</strong></div><div className="email-meta"><span>主题</span><strong>{language === '中文' ? '关于便携式太阳能产品合作' : 'Portable solar products for your range'}</strong></div><div className="email-copy">{body.split('\n').map((line, index) => <p key={`${line}-${index}`}>{line || '\u00a0'}</p>)}</div><div className="evidence-tag"><Icon name="clipboard" size={13}/>内容基于 2 条公开证据</div></div><div className="draft-actions"><button className="more-button" onClick={() => notify('更多操作将在后续阶段接入')}>···</button><button className="outline-button" onClick={() => { setStatus('revision'); notify('已退回修改，已记录审核意见') }}>退回修改</button><button className="primary-button" disabled={status === 'approved'} onClick={() => { setStatus('approved'); notify('草稿已批准，仍未发送邮件') }}><Icon name="check" size={16}/>{status === 'approved' ? '已批准' : '批准草稿'}</button></div></div> }

export default App
