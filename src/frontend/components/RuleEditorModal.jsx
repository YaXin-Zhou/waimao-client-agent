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
      business_offerings: JSON.parse(form.get('business_offerings') || '[]'),
      research_fields: JSON.parse(form.get('research_fields') || '[]'),
    })
  }

  return <div className="modal-backdrop" onClick={onClose}><form className="task-modal rule-editor-modal" onSubmit={submit} onClick={(event) => event.stopPropagation()}>
    <button type="button" className="modal-close" onClick={onClose}>×</button>
    <span className="modal-icon">✦</span><h2>编辑研究规则</h2>
    <p>修改当前任务的业务目录和背调字段，保存后下一次搜索与背调会使用新规则。</p>
    <label>目标产品或服务<input name="product" defaultValue={task.criteria?.product || ''} required /></label>
    <TaskCriteriaBuilder initialCriteria={task.criteria} />
    <button type="submit" className="primary-button full">保存研究规则</button>
  </form></div>
}
