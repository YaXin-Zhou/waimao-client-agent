import { useEffect, useRef, useState } from 'react'

const emptyOffering = () => ({ name: '', key: '', description: '', keywords: '' })
const emptyField = () => ({
  name: '', key: '', description: '', keywords: '', type: 'text',
  required: false, evidence_required: true, human_review: true, options: '',
})

const DEFAULT_OFFERINGS = [
  { name: '注塑件 / Injection molded parts', key: 'injection_molded_parts', description: '判断客户是否确实采购或使用塑料注塑件。', keywords: 'injection molding, injection molded parts, plastic components' },
  { name: 'CNC 机加工 / CNC machined parts', key: 'cnc_machined_parts', description: '判断客户是否确实采购或使用 CNC 精密机加工件。', keywords: 'CNC machining, precision machining, machined parts' },
  { name: '模具与工装 / Molds and tooling', key: 'molds_and_tooling', description: '判断客户是否确实采购模具、工装或相关制造服务。', keywords: 'injection mold, mold making, tooling' },
]

const DEFAULT_FIELDS = [
  { name: '公司全称', key: 'company_full_name', description: '公开来源中的正式公司名称。', keywords: 'company name, legal name, official name', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '注册地址', key: 'registered_address', description: '注册地或公开办公地址。', keywords: 'registered address, registered office, headquarters, office address', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '成立时间', key: 'founded_date', description: '成立年份或成立日期。', keywords: 'founded, established, since, incorporated', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '公司类型', key: 'legal_entity_type', description: 'LLC、Inc、Ltd 等法律主体类型。', keywords: 'LLC, Inc, Ltd, GmbH, company type, legal form', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '社媒链接', key: 'social_profiles', description: 'LinkedIn、Facebook、Instagram 等公开主页。', keywords: 'LinkedIn, Facebook, Instagram, social media', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '电话', key: 'public_phone', description: '官网或其他公开来源中的电话。', keywords: 'phone, telephone, tel, call us', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '主营产品', key: 'main_products', description: '公司公开展示的主要产品或服务。', keywords: 'products, product range, services, solutions', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '业务定位', key: 'business_positioning', description: '品牌方、贸易商、采购方、制造商等业务角色。', keywords: 'brand, distributor, wholesaler, importer, manufacturer, OEM', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '所在行业', key: 'industry', description: '公司公开资料显示的所属行业。', keywords: 'industry, sector, automotive, electronics, medical, industrial', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '产品需求证据', key: 'product_need_evidence', description: '是否确实涉及注塑件、CNC 机加工或模具等产品需求。', keywords: 'plastic parts, injection molding, CNC machining, mold, tooling', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '核心岗位及联系人', key: 'key_contacts', description: 'Sourcing Manager、Purchaser、Engineering Manager、Product Development 等公开联系人。', keywords: 'sourcing manager, purchaser, procurement, engineering manager, product development', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '决策人邮箱', key: 'decision_maker_email', description: '公开来源中的决策人或采购负责人邮箱。', keywords: 'buyer email, purchaser email, sourcing email, procurement email', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '决策人 LinkedIn', key: 'decision_maker_linkedin', description: '公开来源中的决策人 LinkedIn 账号。', keywords: 'buyer LinkedIn, purchaser LinkedIn, sourcing manager LinkedIn', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
  { name: '过往采购品类', key: 'historical_sourcing_categories', description: '公开来源中出现的历史采购或使用品类。', keywords: 'purchasing, procurement, plastic parts, injection molded, CNC parts, molds', type: 'text', required: false, evidence_required: true, human_review: true, options: '' },
]

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

export default function TaskCriteriaBuilder({ initialCriteria = {}, collapsedByDefault = false }) {
  const [offerings, setOfferings] = useState(() => (initialCriteria.business_offerings?.length ? initialCriteria.business_offerings : DEFAULT_OFFERINGS).map((item) => ({ ...item, keywords: Array.isArray(item.keywords) ? item.keywords.join(', ') : item.keywords })))
  const [fields, setFields] = useState(() => (initialCriteria.research_fields?.length ? initialCriteria.research_fields : DEFAULT_FIELDS).map((item) => ({ ...item, type: item.type || 'text', keywords: Array.isArray(item.keywords) ? item.keywords.join(', ') : item.keywords, options: Array.isArray(item.options) ? item.options.join(', ') : item.options })))
  const [expanded, setExpanded] = useState(!collapsedByDefault)
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

  return <details className="criteria-builder criteria-advanced" open={expanded} onToggle={(event) => setExpanded(event.currentTarget.open)}>
    <summary className="criteria-builder-heading"><div><strong>可配置研究规则</strong><p>{expanded ? '已预填当前客户需要的项目，可删除、修改或继续添加。' : '已预填常用规则，不修改也可以直接开始搜索。'}</p></div><span>{serializedOfferings.length + serializedFields.length} 项</span></summary>
    <div className="criteria-builder-content">
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
    </div>
  </details>
}
