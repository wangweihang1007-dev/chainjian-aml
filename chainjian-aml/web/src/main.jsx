import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Archive, ArrowDown, ArrowRight, Bell, CaretDown, ChartLineUp, CheckCircle, ClipboardText,
  FileText, Gear, Graph, MagnifyingGlass, ShieldCheck, SlidersHorizontal, Sparkle, UserCircle,
  WarningCircle, X, Check, Clock, CircleNotch,
} from '@phosphor-icons/react'
import './styles.css'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
  return response.json()
}

const demoAlert = {
  alert_id: 'AL000001', account_id: '20::80032F6C0', risk_score: 90, risk_level: 'HIGH',
  status: 'PENDING', rule_hits: ['CYCLE_TRANSFER', 'RAPID_MOVEMENT'], created_time: '2026-08-02T09:42:31',
}

const navItems = [
  { label: '调查工作台', sub: 'Investigation', icon: ShieldCheck },
  { label: '预警中心', sub: 'Alerts', icon: Bell, badge: '12' },
  { label: '账户画像', sub: 'Profiles', icon: UserCircle },
  { label: '图谱调查', sub: 'Graph', icon: Graph },
  { label: 'Agent 协作', sub: 'Agents', icon: Sparkle },
  { label: '人工审核', sub: 'Review', icon: ClipboardText },
  { label: '评估监控', sub: 'Monitoring', icon: ChartLineUp },
]

function App() {
  const [alerts, setAlerts] = useState([])
  const [selectedId, setSelectedId] = useState('AL000001')
  const [alert, setAlert] = useState(demoAlert)
  const [explainability, setExplainability] = useState(null)
  const [counterfactual, setCounterfactual] = useState(null)
  const [report, setReport] = useState('')
  const [activeTab, setActiveTab] = useState('evidence')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reviewState, setReviewState] = useState('')
  const [search, setSearch] = useState('')
  const [backendConnected, setBackendConnected] = useState(false)

  useEffect(() => {
    api('/alerts').then((data) => {
      setAlerts(data)
      if (data.length) setSelectedId(data[0].alert_id)
    }).catch(() => {
      setBackendConnected(false)
      setAlerts([demoAlert])
    })
  }, [])

  useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([
      api(`/alerts/${encodeURIComponent(selectedId)}`),
      api(`/alerts/${encodeURIComponent(selectedId)}/explainability`),
      api(`/alerts/${encodeURIComponent(selectedId)}/counterfactual`),
    ]).then(([caseData, evidenceData, counterfactualData]) => {
      setBackendConnected(true)
      setAlert(caseData)
      setExplainability(evidenceData)
      setCounterfactual(counterfactualData)
    }).catch((requestError) => {
      setBackendConnected(false)
      setError('后端暂不可用，当前显示演示数据。')
      setAlert(demoAlert)
      setExplainability(null)
      setCounterfactual(null)
    }).finally(() => setLoading(false))
  }, [selectedId])

  const visibleAlerts = useMemo(() => alerts.filter((item) => `${item.alert_id} ${item.account_id}`.toLowerCase().includes(search.toLowerCase())), [alerts, search])
  const evidence = explainability?.evidence_chain?.evidence || []
  const paths = explainability?.evidence_chain?.paths || []
  const transactions = explainability?.evidence_chain?.transactions || []
  const breakdown = explainability?.score_explanation?.score_breakdown || [
    { factor: '规则贡献', score: 40, reason: 'CYCLE_TRANSFER' },
    { factor: '图谱贡献', score: 30, reason: '资金回流路径' },
    { factor: '行为贡献', score: 15, reason: 'RAPID_MOVEMENT' },
    { factor: '账户画像', score: 5, reason: '高频交易' },
  ]

  async function generateReport() {
    try {
      const data = await api(`/reports/${encodeURIComponent(selectedId)}`)
      setReport(data.report_markdown || '')
    } catch {
      setReport('报告服务暂不可用，请确认 FastAPI 已启动。')
    }
  }

  async function submitReview(action) {
    try {
      await api(`/alerts/${encodeURIComponent(selectedId)}/review`, { method: 'POST', body: JSON.stringify({ action, reviewer: 'aml_ops', comment: '通过 React 审查工作台提交' }) })
      setReviewState(action === 'CONFIRM' ? '已确认风险' : action === 'REJECT' ? '已驳回预警' : '已请求补充信息')
      setAlert((previous) => ({ ...previous, status: action === 'CONFIRM' ? 'CONFIRMED' : action === 'REJECT' ? 'REJECTED' : previous.status }))
    } catch {
      setReviewState('审核接口暂不可用')
    }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><ShieldCheck size={23} weight="fill" /></div><div><strong>链鉴</strong><span>AML WORKSPACE</span></div></div>
      <div className="sidebar-section"><span className="eyebrow">合规审查台</span></div>
      <nav>{navItems.map(({ label, sub, icon: Icon, badge }, index) => <button className={`nav-item ${index === 0 ? 'active' : ''}`} key={label}><Icon size={19} weight={index === 0 ? 'fill' : 'regular'} /><span><b>{label}</b><small>{sub}</small></span>{badge && <em>{badge}</em>}</button>)}</nav>
      <div className="sidebar-bottom"><button className="nav-item"><Gear size={19} /><span><b>系统设置</b><small>Settings</small></span></button><div className="operator"><div className="avatar">张</div><div><b>aml_ops</b><small>合规调查组</small></div><CaretDown size={15} /></div></div>
    </aside>

    <main className="main-content">
      <header className="topbar"><div className="breadcrumbs"><span>AML 工作台</span><ArrowRight size={13} /><strong>调查案件</strong><ArrowRight size={13} /><b>{selectedId}</b></div><div className="top-actions"><div className={`connection ${backendConnected ? '' : 'demo-connection'}`}><span className="status-dot" />{backendConnected ? '后端已连接' : '演示模式'}</div><button className="icon-button"><MagnifyingGlass size={18} /></button><button className="icon-button"><Bell size={18} /><i>3</i></button><div className="user-chip"><div className="avatar small">张</div><span>张工</span><CaretDown size={14} /></div></div></header>

      <section className="case-header"><div><span className="eyebrow">案件编号 · CASE ID</span><div className="case-title"><h1>{alert.alert_id}</h1><span className="risk-badge high">{alert.risk_level}</span></div></div><div className="case-meta"><div><span>告警类型</span><b>{(alert.rule_hits || []).join(' · ')}</b></div><div><span>案件状态</span><b className="status-pill">{alert.status === 'PENDING' ? '人工审核中' : alert.status}</b></div><div><span>创建时间</span><b>{alert.created_time?.replace('T', ' ')}</b></div><div><span>涉及账户</span><b>{alert.account_id}</b></div></div><div className="case-actions"><button className="primary-button" onClick={generateReport}><Sparkle size={17} weight="fill" />生成调查报告</button><button className="secondary-button"><Archive size={17} />导出报告</button></div></section>

      {error && <div className="notice"><WarningCircle size={17} />{error}</div>}
      {loading && <div className="loading-line"><CircleNotch size={16} className="spin" />正在加载案件证据…</div>}

      <section className="workspace-grid">
        <div className="transactions-panel panel"><div className="panel-title"><div><span className="eyebrow">证据时间线</span><h2>关键交易 <small>Key Transactions</small></h2></div><button className="icon-button"><SlidersHorizontal size={17} /></button></div><div className="timeline">{(transactions.length ? transactions.slice(0, 6) : demoTransactions).map((tx, index) => <div className="timeline-item" key={tx.transaction_id || tx.id || index}><div className="timeline-dot" /><div className="tx-date">{tx.timestamp || tx.time}</div><div className="tx-card"><div className="tx-top"><span className="tx-id">{tx.transaction_id || tx.id}</span><strong>¥{Number(tx.amount_paid || tx.amount || 0).toLocaleString()}</strong></div><div className="tx-detail"><span>账户 <b>{tx.from_account_id || tx.payer || alert.account_id}</b></span><ArrowRight size={13} /><span>对手方 <b>{tx.to_account_id || tx.receiver || '关联账户'}</b></span></div><small>{tx.payment_format || '转账交易'} · {tx.payment_currency || tx.currency || 'CNY'}</small></div></div>)}</div><button className="view-all">查看全部交易 <ArrowRight size={15} /></button></div>

        <div className="evidence-panel panel"><div className="tabbar">{[['evidence','证据链','Evidence Chain'],['score','评分解释','Score Explanation'],['counterfactual','反事实分析','Counterfactual'],['review','人工审核','Manual Review']].map(([key, label, sub]) => <button className={activeTab === key ? 'selected' : ''} onClick={() => setActiveTab(key)} key={key}><span>{label}</span><small>{sub}</small></button>)}</div>{activeTab === 'evidence' && <EvidenceView evidence={evidence} paths={paths} alert={alert} />}{activeTab === 'score' && <ScoreView breakdown={breakdown} score={alert.risk_score} />}{activeTab === 'counterfactual' && <CounterfactualView data={counterfactual} score={alert.risk_score} />}{activeTab === 'review' && <ReviewView state={reviewState} onSubmit={submitReview} />}</div>

        <aside className="right-rail"><div className="score-card panel"><div className="panel-title"><div><span className="eyebrow">风险评分 · RISK SCORE</span><h2>{alert.risk_score}<small>/ 100</small></h2></div><div className="score-ring"><span>{alert.risk_level}</span></div></div><div className="score-bar"><span style={{ width: `${alert.risk_score}%` }} /></div><div className="score-foot"><span>规则命中 {(alert.rule_hits || []).length}</span><span>证据 {transactions.length || 8} 条</span></div></div><div className="risk-type panel"><span className="eyebrow">风险类型 · RISK TYPE</span><div className="risk-type-row"><WarningCircle size={21} weight="fill" /><div><b>{alert.rule_hits?.[0] || 'CYCLE_TRANSFER'}</b><small>循环转账 · 可疑资金回流</small></div></div></div><div className="report-card panel"><div className="panel-title"><h2>调查报告 <small>Report</small></h2><FileText size={18} /></div>{report ? <div className="report-preview">{report.slice(0, 420)}…</div> : <><p>基于实时证据生成结构化调查报告，包含风险结论、证据链和人工审核建议。</p><button className="report-button" onClick={generateReport}><FileText size={18} />生成调查报告 <ArrowRight size={16} /></button></>}</div></aside>
      </section>
    </main>
  </div>
}

const demoTransactions = [{ transaction_id: 'TX003', timestamp: '2026-08-02 09:05:02', amount_paid: 97500, from_account_id: '20::80032F6C0', to_account_id: '20::80032F6C1', payment_format: '跨行转账' }, { transaction_id: 'TX002', timestamp: '2026-08-02 09:04:12', amount_paid: 98000, from_account_id: '20::80032F6C1', to_account_id: '20::80032F6C2', payment_format: '跨行转账' }, { transaction_id: 'TX001', timestamp: '2026-08-02 09:03:21', amount_paid: 98000, from_account_id: '20::80032F6C2', to_account_id: '20::80032F6C0', payment_format: '跨行转账' }]

function EvidenceView({ evidence, paths, alert }) {
  const primaryPath = evidence.find((item) => item.path)?.path || paths[0]?.account_path?.join(' → ') || 'A001 → B001 → C001 → A001'
  return <div className="evidence-view"><div className="conclusion"><div className="conclusion-icon"><ShieldCheck size={21} weight="fill" /></div><div><span className="eyebrow">风险结论 · RISK CONCLUSION</span><h3>账户存在高风险资金循环行为</h3><p>命中 {alert.rule_hits?.join('、')}，判断基于 Alert、DWD 交易明细和 Neo4j 资金路径。</p></div><button className="text-button">查看详情 <ArrowRight size={15} /></button></div><div className="subsection-heading"><h3>资金路径 <small>Money Path</small></h3><span>证据已核验 <CheckCircle size={15} weight="fill" /></span></div><div className="path-row">{primaryPath.split(/\s*(?:→|->)\s*/).map((node, index, list) => <React.Fragment key={`${node}-${index}`}><div className={`path-node ${index === 0 || index === list.length - 1 ? 'anchor' : ''}`}><b>{node.split('::').pop()}</b><small>{index === 0 || index === list.length - 1 ? '风险账户' : '关联账户'}</small></div>{index < list.length - 1 && <ArrowRight className="path-arrow" size={20} />}</React.Fragment>)}</div><div className="path-caption">路径特征：形成资金回流闭环 · 路径类型：CYCLE_TRANSFER</div><div className="subsection-heading"><h3>证据链 <small>Evidence Chain</small></h3><span>{evidence.length || 2} 条关联证据</span></div><div className="evidence-list">{(evidence.length ? evidence : [{ type: 'cycle_transaction', description: '发现资金回流路径', path: primaryPath }, { type: 'rapid_movement', description: '资金快速流转', holding_time: 15 }]).map((item, index) => <div className="evidence-row" key={index}><div className="evidence-icon">{item.type === 'rapid_movement' ? <Clock size={17} /> : <Graph size={17} />}</div><div><b>{item.description}</b><small>{item.path || (item.holding_time ? `持有时间 ${item.holding_time} 分钟` : '来自 APP Alert Evidence')}</small></div><CheckCircle size={16} weight="fill" className="verified" /></div>)}</div></div>
}

function ScoreView({ breakdown, score }) { return <div className="tab-content"><div className="score-hero"><span className="eyebrow">综合风险评分</span><strong>{score}</strong><span>/ 100 · HIGH</span></div><div className="breakdown-grid">{breakdown.map((item, index) => <div className="breakdown-item" key={`${item.factor}-${index}`}><span>{item.factor}</span><strong>+{item.score}</strong><small>{item.reason}</small></div>)}</div><p className="muted-copy">评分由已落库规则权重与真实查询证据拆解生成，不使用模型补造事实。</p></div> }
function CounterfactualView({ data, score }) { const items = data?.counterfactuals || []; return <div className="tab-content"><div className="counterfactual-hero"><span>当前风险</span><strong>{score}</strong><ArrowRight size={23} /><span>移除关键因素后</span><strong className="after">{items[0]?.score_after_removal || Math.max(score - 45, 0)}</strong></div><div className="cf-list">{(items.length ? items.slice(0, 5) : [{ removed_factor: 'TX003', score_after_removal: 45, impact: 45, explanation: '该交易是资金回流路径中的关键节点' }]).map((item) => <div className="cf-row" key={item.removed_factor}><div><b>移除 {item.removed_factor}</b><small>{item.explanation}</small></div><span>−{item.impact} 分</span><strong>{item.score_after_removal}</strong></div>)}</div><p className="muted-copy">反事实结果仅用于模拟分析，不会修改真实交易或预警数据。</p></div> }
function ReviewView({ state, onSubmit }) { return <div className="tab-content review-view"><span className="eyebrow">人工审核 · MANUAL REVIEW</span><h3>记录案件处置决定</h3><p className="muted-copy">所有操作将写入 review_record 和 audit_log，供后续审计追踪。</p>{state && <div className="review-success"><CheckCircle size={17} weight="fill" />{state}</div>}<button className="review-action confirm" onClick={() => onSubmit('CONFIRM')}><Check size={17} />确认风险</button><button className="review-action reject" onClick={() => onSubmit('REJECT')}><X size={17} />驳回预警</button><button className="review-action more" onClick={() => onSubmit('NEED_MORE_INFO')}><WarningCircle size={17} />需要补充信息</button></div> }

createRoot(document.getElementById('root')).render(<App />)
