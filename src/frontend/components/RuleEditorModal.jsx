import TaskCriteriaBuilder from './TaskCriteriaBuilder'

export default function RuleEditorModal({ task, onClose, onSave }) {
  const submit = (event) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    onSave({
      product: form.get('product'),
      countries: form.get('countries').split(',').map((item) => item.trim()).filter(Boolean),
      customer_types: form.get('customer_types').split(',').map((item) => item.trim()).filter(Boolean),
      language: 'English',
      daily_limit: task.criteria?.daily_limit || 30,
      qualified_lead_limit: Number(form.get('qualified_lead_limit') || 30),
      candidate_limit: Number(form.get('candidate_limit') || 100),
      minimum_qualification_score: Number(form.get('minimum_qualification_score') || 40),
      require_public_email: form.get('require_public_email') === 'on',
      keywords: form.get('keywords').split(',').map((item) => item.trim()).filter(Boolean),
      business_offerings: JSON.parse(form.get('business_offerings') || '[]'),
      research_fields: JSON.parse(form.get('research_fields') || '[]'),
    })
  }

  return <div className="modal-backdrop" onClick={onClose}><form className="task-modal rule-editor-modal" onSubmit={submit} onClick={(event) => event.stopPropagation()}>
    <button type="button" className="modal-close" onClick={onClose}>×</button>
    <span className="modal-icon">✦</span><h2>编辑研究规则</h2>
    <p>修改当前任务的业务目录和背调字段，保存后下一次搜索与背调会使用新规则。</p>
    <label>业务或产品主词（可选）<input name="product" defaultValue={task.criteria?.product || ''} placeholder="没有主词时可只填写业务目录或关键词" /></label>
    <label>补充关键词（逗号分隔）<input name="keywords" defaultValue={(task.criteria?.keywords || []).join(', ')} placeholder="可填写其他语言或行业表达" /></label>
    <label>目标市场（逗号分隔，可选）<input name="countries" defaultValue={(task.criteria?.countries || []).join(', ')} placeholder="例如：Germany, Mexico" /></label>
    <label>客户类型（逗号分隔，可选）<input name="customer_types" defaultValue={(task.criteria?.customer_types || []).join(', ')} placeholder="例如：distributor, manufacturer" /></label>
    <div className="modal-grid qualification-config">
      <label>最终合格客户数<input name="qualified_lead_limit" type="number" min="1" defaultValue={task.criteria?.qualified_lead_limit || 30} /></label>
      <label>候选搜索上限<input name="candidate_limit" type="number" min="1" defaultValue={task.criteria?.candidate_limit || 100} /></label>
      <label>最低匹配分<input name="minimum_qualification_score" type="number" min="0" max="100" defaultValue={task.criteria?.minimum_qualification_score ?? 40} /></label>
    </div>
    <label className="criteria-toggle"><input name="require_public_email" type="checkbox" defaultChecked={task.criteria?.require_public_email ?? true} />最终结果必须有官网公开邮箱</label>
    <TaskCriteriaBuilder initialCriteria={task.criteria} />
    <button type="submit" className="primary-button full">保存研究规则</button>
  </form></div>
}
