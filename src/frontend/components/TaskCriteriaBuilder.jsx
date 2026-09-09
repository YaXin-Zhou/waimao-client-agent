import { useEffect, useRef, useState } from 'react'

const emptyOffering = () => ({ name: '', key: '', description: '', keywords: '' })
const emptyField = () => ({
  name: '', key: '', description: '', keywords: '', type: 'text',
  required: false, evidence_required: true, human_review: true, options: '',
})

function toList(value) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

function toOffering(item) {
  return {
    name: item.name.trim(), key: item.key.trim(), description: item.description.trim(),
    keywords: toList(item.keywords),
  }
}

function toField(item) {
  return {
    name: item.name.trim(), key: item.key.trim(), description: item.description.trim(),
    keywords: toList(item.keywords), type: item.type, required: item.required,
    evidence_required: item.evidence_required, human_review: item.human_review,
    options: toList(item.options),
  }
}

function FieldInput({ label, value, onChange, placeholder }) {
  return <label className="criteria-input">{label}<input value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>
}

export default function TaskCriteriaBuilder() {
  const [offerings, setOfferings] = useState([])
  const [fields, setFields] = useState([])
  const offeringsRef = useRef(null)
  const fieldsRef = useRef(null)
  const update = (setter, index, key, value) => setter((items) => items.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item))
  const serializedOfferings = offerings.filter((item) => item.name.trim() || item.key.trim()).map(toOffering)
  const serializedFields = fields.filter((item) => item.name.trim() || item.key.trim()).map(toField)
  const offeringsJson = JSON.stringify(serializedOfferings)
  const fieldsJson = JSON.stringify(serializedFields)
  useEffect(() => {
    if (offeringsRef.current) offeringsRef.current.value = offeringsJson
    if (fieldsRef.current) fieldsRef.current.value = fieldsJson
  }, [offeringsJson, fieldsJson])

  return <section className="criteria-builder">
    <div className="criteria-builder-heading"><div><strong>可配置研究规则</strong><p>按客户当前目标填写；不需要的项目可以留空。</p></div><span>{serializedOfferings.length + serializedFields.length} 项</span></div>
    <input type="hidden" name="language" defaultValue="English" />
    <textarea hidden ref={offeringsRef} name="business_offerings" readOnly defaultValue="[]" />
    <textarea hidden ref={fieldsRef} name="research_fields" readOnly defaultValue="[]" />

    <div className="criteria-group">
      <div className="criteria-group-title"><div><span className="criteria-index">01</span><strong>业务目录</strong><small>客户要推广的业务或产品</small></div><button type="button" className="criteria-add" onClick={() => setOfferings((items) => [...items, emptyOffering()])}>＋ 添加业务</button></div>
      {offerings.length === 0 && <p className="criteria-empty">暂未配置业务。可以先创建任务，之后再补充。</p>}
      {offerings.map((item, index) => <div className="criteria-card" key={`offering-${index}`}>
        <div className="criteria-card-head"><strong>业务 {index + 1}</strong><button type="button" className="criteria-remove" onClick={() => setOfferings((items) => items.filter((_, itemIndex) => itemIndex !== index))}>移除</button></div>
        <div className="criteria-grid"><FieldInput label="名称" value={item.name} onChange={(value) => update(setOfferings, index, 'name', value)} placeholder="例如：Precision CNC parts" /><FieldInput label="稳定标识 key" value={item.key} onChange={(value) => update(setOfferings, index, 'key', value)} placeholder="例如：cnc_parts" /></div>
        <FieldInput label="关键词（逗号分隔）" value={item.keywords} onChange={(value) => update(setOfferings, index, 'keywords', value)} placeholder="例如：CNC, precision machining" />
        <FieldInput label="业务说明" value={item.description} onChange={(value) => update(setOfferings, index, 'description', value)} placeholder="用于判断客户是否真实需要这项业务" />
      </div>)}
    </div>

    <div className="criteria-group">
      <div className="criteria-group-title"><div><span className="criteria-index">02</span><strong>背调字段</strong><small>需要从公开来源核实的信息</small></div><button type="button" className="criteria-add" onClick={() => setFields((items) => [...items, emptyField()])}>＋ 添加字段</button></div>
      {fields.length === 0 && <p className="criteria-empty">暂未配置额外字段。系统仍会保存核心公司信息和来源证据。</p>}
      {fields.map((item, index) => <div className="criteria-card" key={`field-${index}`}>
        <div className="criteria-card-head"><strong>字段 {index + 1}</strong><button type="button" className="criteria-remove" onClick={() => setFields((items) => items.filter((_, itemIndex) => itemIndex !== index))}>移除</button></div>
        <div className="criteria-grid"><FieldInput label="名称" value={item.name} onChange={(value) => update(setFields, index, 'name', value)} placeholder="例如：公开采购联系人" /><FieldInput label="稳定标识 key" value={item.key} onChange={(value) => update(setFields, index, 'key', value)} placeholder="例如：purchasing_contact" /></div>
        <div className="criteria-grid"><FieldInput label="关键词（逗号分隔）" value={item.keywords} onChange={(value) => update(setFields, index, 'keywords', value)} placeholder="例如：purchasing, sourcing" /><label className="criteria-input">字段类型<select value={item.type} onChange={(event) => update(setFields, index, 'type', event.target.value)}><option value="text">文本</option><option value="number">数字</option><option value="boolean">是 / 否</option><option value="select">选项</option></select></label></div>
        <FieldInput label="字段说明" value={item.description} onChange={(value) => update(setFields, index, 'description', value)} placeholder="说明什么才算有证据支持" />
        {item.type === 'select' && <FieldInput label="允许选项（逗号分隔）" value={item.options} onChange={(value) => update(setFields, index, 'options', value)} placeholder="例如：brand, distributor, manufacturer" />}
        <div className="criteria-checks"><label><input type="checkbox" checked={item.required} onChange={(event) => update(setFields, index, 'required', event.target.checked)} />必须填写</label><label><input type="checkbox" checked={item.evidence_required} onChange={(event) => update(setFields, index, 'evidence_required', event.target.checked)} />必须有来源</label><label><input type="checkbox" checked={item.human_review} onChange={(event) => update(setFields, index, 'human_review', event.target.checked)} />人工复核</label></div>
      </div>)}
    </div>
  </section>
}
