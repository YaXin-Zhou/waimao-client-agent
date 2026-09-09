import TaskCriteriaBuilder from './TaskCriteriaBuilder'

export default function RuleEditorModal({ task, onClose, onSave }) {
  const submit = (event) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    onSave({
      product: form.get('product'),
      countries: task.criteria?.countries || [],
      customer_types: task.criteria?.customer_types || [],
      language: 'English',
      daily_limit: task.criteria?.daily_limit || 10,
      qualified_lead_limit: Number(form.get('qualified_lead_limit') || 10),
      candidate_limit: Number(form.get('candidate_limit') || 50),
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
    <label>目标产品或服务<input name="product" defaultValue={task.criteria?.product || ''} required /></label>
    <label>补充关键词（逗号分隔）<input name="keywords" defaultValue={(task.criteria?.keywords || []).join(', ')} placeholder="可填写其他语言或行业表达" /></label>
    <div className="modal-grid qualification-config">
      <label>最终合格客户数<input name="qualified_lead_limit" type="number" min="1" defaultValue={task.criteria?.qualified_lead_limit || 10} /></label>
      <label>候选搜索上限<input name="candidate_limit" type="number" min="1" defaultValue={task.criteria?.candidate_limit || 50} /></label>
      <label>最低匹配分<input name="minimum_qualification_score" type="number" min="0" max="100" defaultValue={task.criteria?.minimum_qualification_score ?? 40} /></label>
    </div>
    <label className="criteria-toggle"><input name="require_public_email" type="checkbox" defaultChecked={task.criteria?.require_public_email ?? true} />最终结果必须有官网公开邮箱</label>
    <TaskCriteriaBuilder initialCriteria={task.criteria} />
    <button type="submit" className="primary-button full">保存研究规则</button>
  </form></div>
}
