import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Archive, ArrowRight, Bell, CaretDown, ChartLineUp, Check, CheckCircle,
  ClipboardText, Clock, FileText, Gear, Graph, MagnifyingGlass, ShieldCheck,
  SlidersHorizontal, Sparkle, UserCircle, WarningCircle, X, UploadSimple, FilePdf, ImageSquare,
} from '@phosphor-icons/react'
import './styles.css'
import './materials.css'

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true'

async function api(path, options = {}) {
  const token = sessionStorage.getItem('aml.access_token')
  const headers = options.body instanceof FormData ? { ...(options.headers || {}) } : { 'Content-Type': 'application/json', ...(options.headers || {}) }
  if (token && !headers.Authorization) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${API}${path}`, {
    headers,
    ...options,
  })
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`)
  return response.json()
}

async function safeApi(path, options = {}) {
  try { return { ok: true, data: await api(path, options) } } catch (error) { return { ok: false, error } }
}

const demoAlert = {
  alert_id: 'DEMO-000001', account_id: 'DEMO-ACCOUNT', risk_score: 90, risk_level: 'HIGH',
  status: 'PENDING', rule_hits: ['CYCLE_TRANSFER', 'RAPID_MOVEMENT'], created_time: '2026-08-02T09:42:31',
}

const navItems = [
  { label: '调查工作台', sub: 'Investigation', icon: ShieldCheck },
  { label: '预警中心', sub: 'Alerts', icon: Bell },
  { label: '账户画像', sub: 'Profiles', icon: UserCircle },
  { label: '图谱调查', sub: 'Graph', icon: Graph },
  { label: '分析编排', sub: 'Agents', icon: ChartLineUp },
  { label: '人工审核', sub: 'Review', icon: ClipboardText },
  { label: '评估监控', sub: 'Monitoring', icon: ChartLineUp },
]

function normalizeBreakdown(items, total) {
  if (!Array.isArray(items) || items.length === 0 || total == null) return []
  const normalized = items.map((item) => ({ ...item, score: Number(item.score) || 0 }))
  const delta = Number(total) - normalized.reduce((sum, item) => sum + item.score, 0)
  if (Math.abs(delta) > 0.0001) normalized[normalized.length - 1].score += delta
  return normalized
}

function App() {
  const [alerts, setAlerts] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [alert, setAlert] = useState(null)
  const [explainability, setExplainability] = useState(null)
  const [counterfactual, setCounterfactual] = useState(null)
  const [report, setReport] = useState('')
  const [reportError, setReportError] = useState('')
  const [activeTab, setActiveTab] = useState('evidence')
  const [activeNav, setActiveNav] = useState('Investigation')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [backendConnected, setBackendConnected] = useState(false)
  const [search, setSearch] = useState('')
  const [reviewState, setReviewState] = useState('')
  const [reviewer, setReviewer] = useState(() => sessionStorage.getItem('aml.reviewer') || '')
  const [authenticated, setAuthenticated] = useState(() => Boolean(sessionStorage.getItem('aml.access_token')))
  const [loginName, setLoginName] = useState(() => sessionStorage.getItem('aml.reviewer') || '')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [reviewComment, setReviewComment] = useState('')
  const [pendingReviewAction, setPendingReviewAction] = useState('')
  const [reviewSubmitting, setReviewSubmitting] = useState(false)
  const [materials, setMaterials] = useState([])
  const [materialMetrics, setMaterialMetrics] = useState(null)
  const [materialBusy, setMaterialBusy] = useState(false)
  const [materialMessage, setMaterialMessage] = useState('')
  const fileInputRef = useRef(null)
  const [overlay, setOverlay] = useState('')

  useEffect(() => {
    if (!sessionStorage.getItem('aml.access_token')) return
    safeApi('/auth/me').then((result) => {
      if (result.ok) {
        setReviewer(result.data.username)
        setLoginName(result.data.username)
      } else {
        sessionStorage.removeItem('aml.access_token')
        sessionStorage.removeItem('aml.reviewer')
        setAuthenticated(false)
        setReviewer('')
      }
    })
  }, [])

  useEffect(() => {
    safeApi('/alerts').then((result) => {
      if (!result.ok) {
        setBackendConnected(false)
        setAlerts(DEMO_MODE ? [demoAlert] : [])
        setError('后端不可用，当前没有加载任何案件数据。请启动 FastAPI 后重试。')
        if (DEMO_MODE) setSelectedId(demoAlert.alert_id)
        return
      }
      setBackendConnected(true)
      setAlerts(result.data)
      if (result.data.length) setSelectedId(result.data[0].alert_id)
    })
  }, [])

  useEffect(() => {
    if (!selectedId) return
    setLoading(true)
    setError('')
    Promise.all([
      safeApi(`/alerts/${encodeURIComponent(selectedId)}`),
      safeApi(`/alerts/${encodeURIComponent(selectedId)}/explainability`),
      safeApi(`/alerts/${encodeURIComponent(selectedId)}/counterfactual`),
    ]).then(([caseResult, evidenceResult, counterfactualResult]) => {
      setAlert(caseResult.ok ? caseResult.data : null)
      setExplainability(evidenceResult.ok ? evidenceResult.data : null)
      setCounterfactual(counterfactualResult.ok ? counterfactualResult.data : null)
      const failed = [
        !caseResult.ok && '案件详情',
        !evidenceResult.ok && '证据链',
        !counterfactualResult.ok && '反事实分析',
      ].filter(Boolean)
      if (failed.length) setError(`${failed.join('、')}加载失败；页面不会混用演示数据。`)
    }).finally(() => setLoading(false))
  }, [selectedId])

  useEffect(() => {
    if (!selectedId) return
    Promise.all([safeApi(`/alerts/${encodeURIComponent(selectedId)}/materials`), safeApi('/materials/metrics')]).then(([materialsResult, metricsResult]) => {
      setMaterials(materialsResult.ok ? materialsResult.data.materials || [] : [])
      setMaterialMetrics(metricsResult.ok ? metricsResult.data : null)
    })
  }, [selectedId])

  const visibleAlerts = useMemo(
    () => alerts.filter((item) => `${item.alert_id} ${item.account_id}`.toLowerCase().includes(search.toLowerCase())),
    [alerts, search],
  )
  const evidence = explainability?.evidence_chain?.evidence || []
  const paths = explainability?.evidence_chain?.paths || []
  const transactions = explainability?.evidence_chain?.transactions || []
  const breakdown = normalizeBreakdown(explainability?.score_explanation?.score_breakdown, alert?.risk_score)

  async function generateReport() {
    setReportError('')
    const result = await safeApi(`/reports/${encodeURIComponent(selectedId)}`)
    if (!result.ok) { setReport(''); setReportError(`报告生成失败：${result.error.message}`); return }
    setReport(result.data.report_markdown || '')
  }

  function downloadReport() {
    if (!report) return
    const url = URL.createObjectURL(new Blob([report], { type: 'text/markdown;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${selectedId}-investigation-report.md`
    link.click()
    URL.revokeObjectURL(url)
  }

  function printReport() { if (report) window.print() }

  function requestReview(action) {
    if (!authenticated) {
      setReviewState('请先登录审核账号，再提交人工审核。')
      setOverlay('user')
      return
    }
    if (!reviewer.trim() || !reviewComment.trim()) {
      setReviewState('请填写审核人和审核备注后再提交。')
      return
    }
    setPendingReviewAction(action)
  }

  async function login() {
    const username = loginName.trim()
    if (!username || !loginPassword) {
      setLoginError('请输入用户名和密码。')
      return
    }
    const result = await safeApi('/auth/login', { method: 'POST', body: JSON.stringify({ username, password: loginPassword }) })
    if (!result.ok) {
      setLoginError('用户名或密码错误。')
      return
    }
    sessionStorage.setItem('aml.access_token', result.data.access_token)
    sessionStorage.setItem('aml.reviewer', result.data.user.username)
    setReviewer(result.data.user.username)
    setAuthenticated(true)
    setLoginPassword('')
    setLoginError('')
    setOverlay('')
  }

  async function logout() {
    await safeApi('/auth/logout', { method: 'POST' })
    sessionStorage.removeItem('aml.access_token')
    sessionStorage.removeItem('aml.reviewer')
    setAuthenticated(false)
    setReviewer('')
    setLoginName('')
    setOverlay('')
  }

  async function confirmReview() {
    if (!pendingReviewAction) return
    setReviewSubmitting(true)
    const result = await safeApi(`/alerts/${encodeURIComponent(selectedId)}/review`, {
      method: 'POST',
      body: JSON.stringify({ action: pendingReviewAction, reviewer: reviewer.trim(), comment: reviewComment.trim() }),
    })
    if (!result.ok) {
      setReviewState(`审核提交失败：${result.error.message}`)
    } else {
      const action = pendingReviewAction
      setReviewState(action === 'CONFIRM' ? '已确认风险' : action === 'REJECT' ? '已驳回预警' : '已请求补充信息')
      setAlert((previous) => ({ ...previous, status: action === 'CONFIRM' ? 'CONFIRMED' : action === 'REJECT' ? 'REJECTED' : previous.status }))
      setPendingReviewAction('')
    }
    setReviewSubmitting(false)
  }

  async function uploadMaterial(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setMaterialBusy(true)
    setMaterialMessage('正在执行文件校验、OCR、质量和篡改风险检测…')
    const form = new FormData()
    form.append('file', file)
    form.append('material_type', file.type.startsWith('image/') ? 'identity_or_voucher' : 'contract_or_document')
    const result = await safeApi(`/alerts/${encodeURIComponent(selectedId)}/materials`, { method: 'POST', body: form, headers: {} })
    if (result.ok) {
      setMaterials((previous) => [result.data, ...previous])
      setMaterialMessage(result.data.review_route === 'human_review' ? '材料已接收，因识别不确定性或交叉验证差异转人工审核。' : '材料审核完成，可作为案件补充依据。')
    } else setMaterialMessage(`上传失败：${result.error.message}`)
    setMaterialBusy(false)
    event.target.value = ''
  }

  async function decideMaterial(materialId, decision) {
    const form = new FormData()
    form.append('decision', decision)
    form.append('reviewer', reviewer || 'aml_ops')
    form.append('note', '案件补充材料审核')
    const result = await safeApi(`/alerts/${encodeURIComponent(selectedId)}/materials/${encodeURIComponent(materialId)}/decision`, { method: 'POST', body: form, headers: {} })
    if (result.ok) {
      setMaterials((previous) => previous.map((item) => item.material_id === materialId ? result.data : item))
      setMaterialMessage('材料审核决定已记录。')
    } else setMaterialMessage(`审核提交失败：${result.error.message}`)
  }

  if (!alert) return <EmptyState error={error} connected={backendConnected} />

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><ShieldCheck size={23} weight="fill" /></div><div><strong>链鉴</strong><span>AML WORKSPACE</span></div></div>
      <div className="sidebar-section"><span className="eyebrow">研究与审查平台</span></div>
      <nav aria-label="主导航">{navItems.map(({ label, sub, icon: Icon }) => <button aria-label={`${label} ${sub}`} className={`nav-item ${activeNav === sub ? 'active' : ''}`} onClick={() => setActiveNav(sub)} key={sub}><Icon size={19} weight={activeNav === sub ? 'fill' : 'regular'} /><span><b>{label}</b><small>{sub}</small></span></button>)}</nav>
      <div className="sidebar-bottom"><button aria-label="系统设置" className="nav-item" onClick={() => { setActiveNav('Settings'); setOverlay('') }}><Gear size={19} /><span><b>系统设置</b><small>Settings</small></span></button><button aria-label="打开用户菜单" className="operator operator-button" onClick={() => setOverlay(overlay === 'user' ? '' : 'user')}><div className="avatar">审</div><div><b>{reviewer || '未登录'}</b><small>合规调查组</small></div><CaretDown size={15} /></button></div>
    </aside>
    <main className="main-content">
      {activeNav === 'Investigation' ? <>
      {overlay && <OverlayPanel kind={overlay} reviewer={reviewer} authenticated={authenticated} loginName={loginName} loginPassword={loginPassword} loginError={loginError} setLoginName={setLoginName} setLoginPassword={setLoginPassword} onClose={() => setOverlay('')} onLogin={login} onLogout={logout} />}
      <header className="topbar"><div className="breadcrumbs"><span>AML 工作台</span><ArrowRight size={13} /><strong>调查案件</strong><ArrowRight size={13} /><b>{selectedId}</b></div><div className="top-actions"><div className={`connection ${backendConnected ? '' : 'demo-connection'}`}><span className="status-dot" />{backendConnected ? '后端已连接' : '演示模式'}</div><label className="search-box"><MagnifyingGlass size={16} /><input aria-label="搜索案件" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索案件" /></label><button aria-label="通知" className="icon-button" onClick={() => setOverlay(overlay === 'notifications' ? '' : 'notifications')}><Bell size={18} /></button><button aria-label="打开登录菜单" className="user-chip" onClick={() => setOverlay(overlay === 'user' ? '' : 'user')}><div className="avatar small">审</div><span>{reviewer || '未登录'}</span><CaretDown size={14} /></button></div></header>
      <section className="case-header"><div><span className="eyebrow">案件编号 · CASE ID</span><div className="case-title"><h1>{alert.alert_id}</h1><span className="risk-badge high">{alert.risk_level}</span></div></div><div className="case-meta"><div><span>预警类型</span><b>{(alert.rule_hits || []).join(' · ')}</b></div><div><span>案件状态</span><b className="status-pill">{alert.status}</b></div><div><span>创建时间</span><b>{alert.created_time?.replace('T', ' ')}</b></div><div><span>涉及账户</span><b>{alert.account_id}</b></div></div><div className="case-actions"><button className="primary-button" onClick={generateReport}><Sparkle size={17} weight="fill" />生成调查报告</button><button className="secondary-button" onClick={downloadReport} disabled={!report} aria-label="下载 Markdown 报告"><Archive size={17} />导出 Markdown</button><button className="secondary-button" onClick={printReport} disabled={!report} aria-label="打印或保存 PDF 报告"><FileText size={17} />保存 PDF</button></div></section>
      {error && <div className="notice" role="alert"><WarningCircle size={17} />{error}</div>}
      {loading && <div className="loading-line">正在加载案件证据…</div>}
      {activeTab === 'materials' && <MaterialsView materials={materials} metrics={materialMetrics} busy={materialBusy} message={materialMessage} inputRef={fileInputRef} onUpload={uploadMaterial} onDecision={decideMaterial} />}
      <section className="workspace-grid">
        <div className="transactions-panel panel"><div className="panel-title"><div><span className="eyebrow">证据时间线</span><h2>关键交易 <small>Key Transactions</small></h2></div><button aria-label="交易筛选" className="icon-button" onClick={() => setOverlay(overlay === 'filter' ? '' : 'filter')}><SlidersHorizontal size={17} /></button></div>{overlay === 'filter' && <div className="inline-tool-panel"><b>交易筛选</b><span>当前展示与案件证据相关的前 6 笔交易</span><button className="text-button" onClick={() => setOverlay('')}>关闭</button></div>}<div className="timeline">{transactions.length ? transactions.slice(0, 6).map((tx, index) => <Transaction key={tx.transaction_id || tx.id || index} tx={tx} accountId={alert.account_id} />) : <EmptyPanel text="暂无可验证交易证据" />}</div></div>
        <div className="evidence-panel panel" style={{ display: activeTab === 'materials' ? 'none' : undefined }}><div className="tabbar" role="tablist"><button role="tab" aria-selected={activeTab === 'materials'} className={activeTab === 'materials' ? 'selected' : ''} onClick={() => setActiveTab('materials')}><span>补充材料</span><small>Materials Review</small></button>{[['evidence', '证据链', 'Evidence Chain'], ['score', '评分解释', 'Score Explanation'], ['counterfactual', '反事实分析', 'Counterfactual'], ['review', '人工审核', 'Manual Review']].map(([key, label, sub]) => <button role="tab" aria-selected={activeTab === key} className={activeTab === key ? 'selected' : ''} onClick={() => setActiveTab(key)} key={key}><span>{label}</span><small>{sub}</small></button>)}</div>{activeTab === 'evidence' && <EvidenceView evidence={evidence} paths={paths} alert={alert} />}{activeTab === 'score' && <ScoreView breakdown={breakdown} score={alert.risk_score} />}{activeTab === 'counterfactual' && <CounterfactualView data={counterfactual} score={alert.risk_score} />}{activeTab === 'review' && <ReviewView state={reviewState} reviewer={reviewer} comment={reviewComment} pendingAction={pendingReviewAction} submitting={reviewSubmitting} setReviewer={setReviewer} setComment={setReviewComment} onSubmit={requestReview} onConfirm={confirmReview} onCancel={() => setPendingReviewAction('')} />}</div>
        <aside className="right-rail"><div className="score-card panel"><div className="panel-title"><div><span className="eyebrow">风险评分 · RISK SCORE</span><h2>{alert.risk_score}<small>/ 100</small></h2></div><div className="score-ring"><span>{alert.risk_level}</span></div></div><div className="score-bar"><span style={{ width: `${Math.min(Number(alert.risk_score) || 0, 100)}%` }} /></div><div className="score-foot"><span>规则命中 {(alert.rule_hits || []).length}</span><span>证据 {evidence.length} 条</span></div></div><div className="report-card panel"><div className="panel-title"><h2>调查报告 <small>Report</small></h2><FileText size={18} /></div>{reportError && <div className="inline-error" role="alert">{reportError}</div>}{report ? <><div className="report-preview">{report.slice(0, 420)}…</div><div className="report-actions"><button className="report-button" onClick={downloadReport}>下载 Markdown</button><button className="report-button" onClick={printReport}>打印 / 保存 PDF</button></div></> : <><p>基于当前案件证据生成结构化调查报告。</p><button className="report-button" onClick={generateReport}><FileText size={18} />生成调查报告 <ArrowRight size={16} /></button></>}</div><div className="alert-list panel"><div className="panel-title"><h2>案件列表 <small>{visibleAlerts.length}</small></h2></div>{visibleAlerts.slice(0, 6).map((item) => <button className={`alert-row ${item.alert_id === selectedId ? 'selected' : ''}`} key={item.alert_id} onClick={() => setSelectedId(item.alert_id)}><span>{item.alert_id}</span><b>{item.risk_score}</b></button>)}</div></aside>
      </section>
      </> : <NavigationPage activeNav={activeNav} alerts={visibleAlerts} alert={alert} selectedId={selectedId} onSelectAlert={(id) => { setSelectedId(id); setActiveNav('Investigation') }} />}
    </main>
  </div>
}

function EmptyState({ error, connected }) { return <div className="empty-state"><ShieldCheck size={42} /><h1>暂无可展示案件</h1><p>{error || (connected ? '案件列表为空。' : '请启动后端服务后刷新页面。')}</p></div> }
function EmptyPanel({ text }) { return <div className="empty-panel"><WarningCircle size={20} /><span>{text}</span></div> }
function Transaction({ tx, accountId }) { const currency = tx.payment_currency || tx.currency || 'CNY'; const symbol = currency === 'Euro' ? '€' : currency === 'US Dollar' || currency === 'USD' ? '$' : currency === 'Chinese Yuan' || currency === 'CNY' ? '¥' : ''; return <div className="timeline-item"><div className="timeline-dot" /><div className="tx-date">{tx.timestamp || tx.time}</div><div className="tx-card"><div className="tx-top"><span className="tx-id">{tx.transaction_id || tx.id}</span><strong>{symbol}{Number(tx.amount_paid || tx.amount || 0).toLocaleString()} {symbol ? '' : currency}</strong></div><div className="tx-detail"><span>账户 <b>{tx.from_account_id || tx.payer || accountId}</b></span><ArrowRight size={13} /><span>对手方 <b>{tx.to_account_id || tx.receiver || '未知'}</b></span></div><small>{tx.payment_format || '转账交易'} · {currency}</small></div></div> }
function EvidenceView({ evidence, paths, alert }) { const path = evidence.find((item) => item.path)?.path || paths[0]?.account_path?.join(' → ') || ''; return <div className="evidence-view"><div className="conclusion"><div className="conclusion-icon"><ShieldCheck size={21} weight="fill" /></div><div><span className="eyebrow">风险结论 · RISK CONCLUSION</span><h3>{evidence.length ? '发现可疑资金流转行为' : '暂无可验证证据'}</h3><p>{evidence.length ? `命中 ${(alert.rule_hits || []).join('、')}，结论仅基于当前证据链。` : '后端未返回证据，不能生成风险结论。'}</p></div></div><div className="subsection-heading"><h3>资金路径 <small>Money Path</small></h3></div>{path ? <div className="path-row">{path.split(/\s*(?:→|->)\s*/).map((node, index, list) => <React.Fragment key={`${node}-${index}`}><div className="path-node"><b>{node.split('::').pop()}</b><small>{index === 0 || index === list.length - 1 ? '风险账户' : '关联账户'}</small></div>{index < list.length - 1 && <ArrowRight className="path-arrow" size={20} />}</React.Fragment>)}</div> : <EmptyPanel text="暂无可验证资金路径" />}<div className="subsection-heading"><h3>证据链 <small>Evidence Chain</small></h3><span>{evidence.length} 条</span></div><div className="evidence-list">{evidence.length ? evidence.map((item, index) => <div className="evidence-row" key={index}><div className="evidence-icon">{item.type === 'rapid_movement' ? <Clock size={17} /> : <Graph size={17} />}</div><div><b>{item.description || item.evidence_type}</b><small>{item.path || '来自 APP Alert Evidence'}</small></div><CheckCircle size={16} weight="fill" className="verified" /></div>) : <EmptyPanel text="暂无可验证证据" />}</div></div> }
function ScoreView({ breakdown, score }) { const sum = breakdown.reduce((total, item) => total + Number(item.score || 0), 0); return <div className="tab-content"><div className="score-hero"><span className="eyebrow">综合风险评分</span><strong>{score ?? '—'}</strong><span>/ 100</span></div>{breakdown.length ? <><div className="breakdown-grid">{breakdown.map((item, index) => <div className="breakdown-item" key={`${item.factor}-${index}`}><span>{item.factor}</span><strong>+{item.score}</strong><small>{item.reason}</small></div>)}</div><p className="score-total">分项合计：{sum} / 总分：{score}</p></> : <EmptyPanel text="暂无评分拆解，不能推断风险贡献" />}</div> }
function CounterfactualView({ data, score }) { const items = data?.counterfactuals || []; return <div className="tab-content">{items.length ? <><div className="counterfactual-hero"><span>当前风险</span><strong>{score}</strong><ArrowRight size={23} /><span>移除关键因素后</span><strong className="after">{items[0].score_after_removal}</strong></div><div className="cf-list">{items.slice(0, 5).map((item) => <div className="cf-row" key={item.removed_factor}><div><b>移除 {item.removed_factor}</b><small>{item.explanation}</small></div><span>−{item.impact} 分</span><strong>{item.score_after_removal}</strong></div>)}</div></> : <EmptyPanel text="暂无反事实分析结果" />}<p className="muted-copy">反事实结果仅用于模拟分析，不会修改真实交易或预警数据。</p></div> }
function ReviewView({ state, reviewer, comment, pendingAction, submitting, setReviewer, setComment, onSubmit, onConfirm, onCancel }) { return <div className="tab-content review-view"><span className="eyebrow">人工审核 · MANUAL REVIEW</span><h3>记录案件处置决定</h3><p className="muted-copy">审核人和备注为必填项，提交前需要二次确认。</p><label className="field-label">审核人<input aria-label="审核人" value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="例如：compliance.reviewer" /></label><label className="field-label">审核备注<textarea aria-label="审核备注" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="说明判断依据和后续动作" rows="4" /></label>{state && <div className="review-success" role="status"><CheckCircle size={17} weight="fill" />{state}</div>}<button className="review-action confirm" onClick={() => onSubmit('CONFIRM')}><Check size={17} />确认风险</button><button className="review-action reject" onClick={() => onSubmit('REJECT')}><X size={17} />驳回预警</button><button className="review-action more" onClick={() => onSubmit('NEED_MORE_INFO')}><WarningCircle size={17} />需要补充信息</button>{pendingAction && <div className="confirm-dialog" role="dialog" aria-modal="true"><h4>确认提交审核决定？</h4><p>操作：{pendingAction}。提交后会写入 review_record 和 audit_log。</p><div><button className="secondary-button" onClick={onCancel} disabled={submitting}>取消</button><button className="primary-button" onClick={onConfirm} disabled={submitting}>{submitting ? '提交中…' : '确认提交'}</button></div></div>}</div> }

function MaterialsView({ materials, metrics, busy, message, inputRef, onUpload, onDecision }) {
  return <div className="tab-content materials-view"><div className="materials-hero"><div><span className="eyebrow">案件补充材料 · MULTIMODAL REVIEW</span><h3>上传身份证明、合同或交易凭证</h3><p className="muted-copy">系统将执行 OCR、图片质量、篡改风险和流水交叉验证；无法可靠判断的材料自动转人工审核。</p></div><label className={`upload-dropzone ${busy ? 'busy' : ''}`}><input ref={inputRef} type="file" accept=".jpg,.jpeg,.png,.webp,.pdf,.docx,.txt" onChange={onUpload} disabled={busy} /><UploadSimple size={22} /><b>{busy ? '智能审核中…' : '选择材料上传'}</b><small>图片 / PDF / DOCX，单个不超过 20MB</small></label></div>{message && <div className="material-message"><CheckCircle size={16} />{message}</div>}{metrics && <div className="material-metrics"><span><b>{metrics.materials_reviewed}</b>已审核材料</span><span><b>{Math.round(metrics.human_review_rate * 100)}%</b>转人工</span><span><b>{Math.round(metrics.avg_confidence * 100)}%</b>平均置信度</span><span><b>{metrics.demo_baseline?.estimated_time_saved}</b>预计节省调查时间</span></div>}<div className="subsection-heading"><h3>已上传材料 <small>{materials.length} files</small></h3><span><ShieldCheck size={15} />结果可追溯</span></div>{materials.length === 0 ? <EmptyPanel text="暂无补充材料" /> : <div className="material-list">{materials.map((material) => <MaterialCard key={material.material_id} material={material} onDecision={onDecision} />)}</div>}</div>
}

function MaterialCard({ material, onDecision }) {
  const quality = material.quality_check || {}
  const tamper = material.tamper_check || {}
  const ocr = material.ocr || {}
  const cross = material.cross_validation || {}
  const icon = material.extension === '.pdf' ? <FilePdf size={20} /> : material.extension === '.docx' ? <FileText size={20} /> : <ImageSquare size={20} />
  return <div className="material-card"><div className="material-card-head"><div className="material-file-icon">{icon}</div><div><b>{material.filename}</b><small>{material.material_id} · SHA {material.sha256?.slice(0, 10)}</small></div><span className={`material-status ${material.status}`}>{material.review_route === 'human_review' ? '待人工审核' : material.status === 'accepted' ? '已通过' : '智能审核通过'}</span></div><div className="material-checks"><span className={quality.status === 'passed' ? 'passed' : 'warning'}><CheckCircle size={14} />质量：{quality.quality || '文件'}</span><span className={tamper.status === 'no_obvious_signal' ? 'passed' : tamper.status === 'not_applicable' ? 'neutral' : 'warning'}><ShieldCheck size={14} />篡改：{tamper.status === 'no_obvious_signal' ? '未发现明显信号' : tamper.status === 'not_applicable' ? '不适用' : '需关注'}</span><span className={ocr.status === 'completed' ? 'passed' : 'warning'}><FileText size={14} />OCR：{ocr.status === 'completed' ? `已提取（${Math.round(ocr.confidence * 100)}%）` : '需人工'}</span><span className={cross.status === 'warning' ? 'warning' : cross.status === 'passed' ? 'passed' : 'neutral'}><WarningCircle size={14} />交叉验证：{cross.status === 'warning' ? '发现不一致' : cross.status === 'passed' ? '一致' : '未执行'}</span><span className="neutral">置信度：{Math.round((material.confidence || 0) * 100)}%</span></div>{cross.discrepancies?.length > 0 && <div className="ocr-preview">关注项：{cross.discrepancies.join('；')}</div>}{ocr.text && <div className="ocr-preview">{ocr.text.slice(0, 180)}</div>}{material.review_route === 'human_review' && <div className="material-actions"><button className="review-action confirm" onClick={() => onDecision(material.material_id, 'ACCEPT')}><Check size={15} />人工通过</button><button className="review-action reject" onClick={() => onDecision(material.material_id, 'REJECT')}><X size={15} />退回材料</button></div>}</div>
}

function NavigationPage({ activeNav, alerts, alert, selectedId, onSelectAlert }) {
  const [data, setData] = useState(null)
  const [query, setQuery] = useState('')
  const [alertPage, setAlertPage] = useState(1)
  const [agentInput, setAgentInput] = useState(`分析 ${selectedId}`)
  const [agentResult, setAgentResult] = useState(null)
  const [agentBusy, setAgentBusy] = useState(false)
  const filteredAlerts = alerts.filter((item) => `${item.alert_id} ${item.account_id}`.toLowerCase().includes(query.toLowerCase()))
  useEffect(() => setAlertPage(1), [query])

  useEffect(() => {
    setData(null)
    setAgentResult(null)
    const endpoint = { Profiles: `/accounts/${encodeURIComponent(alert.account_id)}/profile`, Graph: `/alerts/${encodeURIComponent(selectedId)}/graph-intelligence`, Review: '/reviews/pending', Monitoring: '/monitoring/metrics' }[activeNav]
    if (endpoint) {
      const requests = [safeApi(endpoint)]
      if (activeNav === 'Monitoring') requests.push(safeApi('/evaluation/metrics'), safeApi('/iteration/status'))
      Promise.all(requests).then(([result, evaluationResult, iterationResult]) => {
        if (!result.ok) {
          setData({ error: result.error.message })
          return
        }
        setData({
          ...result.data,
          ...(activeNav === 'Monitoring' && evaluationResult?.ok ? { evaluation: evaluationResult.data } : {}),
          ...(activeNav === 'Monitoring' && iterationResult?.ok ? { iteration: iterationResult.data } : {}),
        })
      })
    }
  }, [activeNav, alert.account_id, selectedId])

  async function investigate() {
    if (agentBusy) return
    setAgentBusy(true)
    setAgentResult({ pending: true, ai: { enabled: true, provider: 'MiniMax', model: 'MiniMax-M2.5' }, results: { alert: { alert_id: selectedId }, explainability: { risk_explanation: { conclusion: '正在读取案件证据并调用 MiniMax，请稍候…' } } } })
    try {
      const result = await safeApi('/agent/multi-investigate', { method: 'POST', body: JSON.stringify({ user_input: agentInput }) })
      setAgentResult(result.ok ? result.data : { error: result.error.message })
    } finally {
      setAgentBusy(false)
    }
  }

  const titles = { Alerts: ['预警中心', '集中查看、筛选并进入调查案件'], Profiles: ['账户画像', '查看当前账户的行为特征与风险画像'], Graph: ['图谱调查', '查看关联账户、资金路径和关联核查线索'], Agents: ['分析编排', '基于当前案件证据执行结构化分析'], Review: ['人工审核', '处理待审核案件并进入证据审查'], Monitoring: ['评估监控', '查看规则质量与系统运行指标'] }
  const [title, subtitle] = titles[activeNav] || ['系统设置', '当前 React 工作台配置']
  return <div className="section-page">
    <div className="section-page-head"><div><span className="eyebrow">{activeNav}</span><h1>{title}</h1><p>{subtitle}</p></div><span className="connection"><span className="status-dot" />实时数据</span></div>
    {activeNav === 'Alerts' && <AlertsPage alerts={filteredAlerts} page={alertPage} onPageChange={setAlertPage} onSelectAlert={onSelectAlert} query={query} onQueryChange={setQuery} />}
    {activeNav === 'Profiles' && <ProfilePage alert={alert} data={data} />}
    {activeNav === 'Graph' && <GraphPage data={data} alert={alert} />}
    {activeNav === 'Agents' && <div className="page-panel panel agent-page"><label className="field-label">调查问题<textarea aria-label="调查问题" value={agentInput} onChange={(event) => setAgentInput(event.target.value)} rows="3" /></label><button className="primary-button" onClick={investigate} disabled={agentBusy}><Sparkle size={17} />{agentBusy ? 'Agent 分析中…' : '开始 Agent 调查'}</button>{agentBusy && <div className="agent-busy">正在读取案件证据并调用 MiniMax，请稍候…</div>}{agentResult && <><div className="agent-ai-status">{agentResult.ai?.enabled ? `已调用 ${agentResult.ai.provider} AI · ${agentResult.ai.model}` : '模型不可用，使用证据型本地回退'}</div><AgentReply result={agentResult} /></>}</div>}
    {activeNav === 'Review' && <ReviewQueue data={data} onSelect={onSelectAlert} />}
    {activeNav === 'Monitoring' && <><QualityModePanel /><IndustryBenchmarkPanel /><MonitoringPage data={data} /></>}
    {!['Alerts', 'Profiles', 'Graph', 'Agents', 'Review', 'Monitoring'].includes(activeNav) && <SettingsPage />}
  </div>
}

function AlertsPage({ alerts, page, onPageChange, onSelectAlert, query, onQueryChange }) {
  const start = (page - 1) * 50
  const visible = alerts.slice(start, start + 50)
  return <div className="page-panel panel"><div className="toolbar"><input aria-label="筛选预警" value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="按案件号或账户筛选" /><span>{alerts.length} 条预警</span></div><div className="data-table">{visible.map((item) => <button className="data-row" key={item.alert_id} onClick={() => onSelectAlert(item.alert_id)}><span><b>{item.alert_id}</b><small>{item.account_id}</small></span><strong className="risk-number">{item.risk_score}</strong><span>{item.risk_level}</span><span>{item.status}</span><ArrowRight size={16} /></button>)}</div>{alerts.length > 50 && <div className="pagination"><span>显示 {start + 1}–{Math.min(start + visible.length, alerts.length)} / {alerts.length}</span><button className="text-button" disabled={page === 1} onClick={() => onPageChange((value) => Math.max(1, value - 1))}>上一页</button><button className="text-button" disabled={start + 50 >= alerts.length} onClick={() => onPageChange((value) => value + 1)}>下一页</button></div>}</div>
}

function ProfilePage({ alert, data }) { return <div className="page-panel panel"><div className="profile-hero"><div className="avatar large"><UserCircle size={26} /></div><div><h2>{alert.account_id}</h2><p>当前案件：{alert.alert_id} · 风险等级：{alert.risk_level}</p></div></div>{data?.error ? <EmptyPanel text={data.error} /> : <div className="metric-grid">{[['交易笔数', data?.txn_count], ['交易对手数', data?.counterparty_count], ['活跃天数', data?.active_days], ['风险特征', data?.risk_features?.join('、')]].map(([label, value]) => <div className="metric-card" key={label}><span>{label}</span><strong>{value ?? '加载中…'}</strong></div>)}</div>}</div> }
function GraphPage({ data, alert }) { const paths = data?.paths || (alert.evidence || []).map((item) => ({ account_path: item.evidence_content?.account_path || [] })); const graph = data?.evidence_subgraph || buildGraphFromPaths(paths); const associated = data?.associated_review || []; const reasons = (alert.rule_hits || []).map((hit) => ({ code: hit, label: ({ DAILY_ACTIVITY_ANOMALY: '\u65e5\u5185\u4ea4\u6613\u6d3b\u52a8\u5f02\u5e38', FAN_IN_COLLECTION: '\u591a\u4e2a\u8d26\u6237\u6c47\u5165\u540c\u4e00\u8d26\u6237\uff0c\u7591\u4f3c\u8d44\u91d1\u5f52\u96c6', RAPID_MOVEMENT: '\u77ed\u65f6\u95f4\u5185\u5feb\u901f\u8f6c\u79fb\u8d44\u91d1', STRUCTURING_TRANSFER: '\u62c6\u5206\u4ea4\u6613\u89c4\u907f\u76d1\u6d4b\u9608\u503c', CYCLE_TRANSFER: '\u8d44\u91d1\u5faa\u73af\u56de\u6d41\uff0c\u5f62\u6210\u95ed\u73af', FAN_OUT_DISTRIBUTION: '\u5355\u4e00\u8d26\u6237\u5411\u591a\u4e2a\u8d26\u6237\u5206\u6563\u8f6c\u51fa' }[hit] || hit) })); return <div className="graph-page-grid"><div className="page-panel panel graph-panel"><div className="graph-panel-head"><div><h2>资金关系图（Neo4j / SQLite）</h2><p>力导向布局来自真实资金关系；滚轮缩放、空白处拖动画布、节点可拖拽，点击关系查看交易和预警原因。</p></div><span className="graph-legend"><i className="legend-dot alert" />预警触发关系 <i className="legend-dot direct" />风险账户 <i className="legend-dot related" />关联线索</span></div>{reasons.length > 0 && <div className="alert-reasons"><span>本案预警原因：</span>{reasons.map((item) => <span className="alert-reason-chip" key={item.code}>{item.label}</span>)}</div>}{graph.nodes?.length ? <GraphCanvas graph={graph} directAccount={alert.account_id} /> : <EmptyPanel text={`暂未返回 ${alert.account_id} 的图谱数据`} />}</div><div className="page-panel panel"><h2>关联核查线索</h2>{associated.length ? associated.map((item) => <div className="graph-path" key={item.account_id}><WarningCircle size={18} /><span>{item.account_id} · {item.classification}</span></div>) : <EmptyPanel text={data?.error || '暂无关联核查线索'} />}</div></div> }

function buildGraphFromPaths(paths) { const nodes = new Set(); const edges = []; paths.forEach((path) => { const accounts = path.account_path || path.path || []; accounts.forEach((account) => nodes.add(account)); for (let index = 0; index < accounts.length - 1; index += 1) edges.push({ source: accounts[index], target: accounts[index + 1], evidence_type: 'direct_hit' }); }); return { nodes: [...nodes].map((account_id) => ({ account_id, evidence_type: 'direct_hit' })), edges }; }

function GraphCanvas({ graph, directAccount }) {
  const stageWidth = 920
  const stageHeight = 560
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const nodeMap = Object.fromEntries(nodes.map((node) => [node.account_id, node]))
  const [positions, setPositions] = useState(() => seedGraphPositions(nodes, stageWidth, stageHeight))
  const [selected, setSelected] = useState(null)
  const [selectedEdge, setSelectedEdge] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const physics = useRef({ positions: seedGraphPositions(nodes, stageWidth, stageHeight), fixed: {}, running: true })
  const dragRef = useRef(null)
  const panRef = useRef(null)

  useEffect(() => {
    const state = physics.current
    state.positions = seedGraphPositions(nodes, stageWidth, stageHeight)
    state.fixed = {}
    state.running = true
    setPositions(state.positions)
    let frame = 0
    let raf
    function tick() {
      const current = state.positions
      const next = Object.fromEntries(nodes.map((node) => [node.account_id, { ...current[node.account_id] }]))
      nodes.forEach((node) => {
        const id = node.account_id
        if (state.fixed[id]) return
        let fx = (stageWidth / 2 - current[id].x) * 0.006
        let fy = (stageHeight / 2 - current[id].y) * 0.006
        nodes.forEach((other) => {
          if (other.account_id === id) return
          const dx = current[id].x - current[other.account_id].x
          const dy = current[id].y - current[other.account_id].y
          const distance = Math.max(Math.hypot(dx, dy), 18)
          const force = 1800 / (distance * distance)
          fx += (dx / distance) * force
          fy += (dy / distance) * force
        })
        edges.forEach((edge) => {
          if (edge.source !== id && edge.target !== id) return
          const otherId = edge.source === id ? edge.target : edge.source
          const dx = current[otherId].x - current[id].x
          const dy = current[otherId].y - current[id].y
          const distance = Math.max(Math.hypot(dx, dy), 1)
          const force = Math.min(distance * 0.004, 0.9)
          fx += dx / distance * force
          fy += dy / distance * force
        })
        next[id].x = Math.max(34, Math.min(stageWidth - 34, current[id].x + fx))
        next[id].y = Math.max(34, Math.min(stageHeight - 34, current[id].y + fy))
      })
      state.positions = next
      setPositions(next)
      frame += 1
      if (state.running && frame < 260) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { state.running = false; cancelAnimationFrame(raf) }
  }, [graph])

  function reset() { setPan({ x: 0, y: 0 }); setZoom(1); physics.current.positions = seedGraphPositions(nodes, stageWidth, stageHeight); physics.current.fixed = {}; physics.current.running = true; setPositions(physics.current.positions) }
  function moveNode(id, event) {
    if (!dragRef.current || dragRef.current.id !== id) return
    const rect = event.currentTarget.closest('.interactive-graph').getBoundingClientRect()
    const x = (event.clientX - rect.left - pan.x) / zoom
    const y = (event.clientY - rect.top - pan.y) / zoom
    const point = { x: Math.max(34, Math.min(stageWidth - 34, x)), y: Math.max(34, Math.min(stageHeight - 34, y)) }
    physics.current.positions[id] = point
    setPositions({ ...physics.current.positions })
  }
  function beginNodeDrag(id, event) { event.stopPropagation(); event.currentTarget.setPointerCapture(event.pointerId); physics.current.fixed[id] = true; dragRef.current = { id } }
  function endNodeDrag() { dragRef.current = null }
  function beginPan(event) { if (event.target !== event.currentTarget) return; panRef.current = { x: event.clientX, y: event.clientY, pan }; event.currentTarget.setPointerCapture(event.pointerId) }
  function movePan(event) { if (!panRef.current) return; setPan({ x: panRef.current.pan.x + event.clientX - panRef.current.x, y: panRef.current.pan.y + event.clientY - panRef.current.y }) }
  function endPan() { panRef.current = null }
  const ruleReason = { DAILY_ACTIVITY_ANOMALY: '\u65e5\u5185\u4ea4\u6613\u6d3b\u52a8\u5f02\u5e38', FAN_IN_COLLECTION: '\u591a\u4e2a\u8d26\u6237\u6c47\u5165\u540c\u4e00\u8d26\u6237\uff0c\u7591\u4f3c\u8d44\u91d1\u5f52\u96c6', RAPID_MOVEMENT: '\u77ed\u65f6\u95f4\u5185\u5feb\u901f\u8f6c\u79fb\u8d44\u91d1', STRUCTURING_TRANSFER: '\u62c6\u5206\u4ea4\u6613\u89c4\u907f\u76d1\u6d4b\u9608\u503c', CYCLE_TRANSFER: '\u8d44\u91d1\u5faa\u73af\u56de\u6d41\uff0c\u5f62\u6210\u95ed\u73af', FAN_OUT_DISTRIBUTION: '\u5355\u4e00\u8d26\u6237\u5411\u591a\u4e2a\u8d26\u6237\u5206\u6563\u8f6c\u51fa' }
  function reason(edge) { const rule = edge.rule_hit || edge.rule_code; return ruleReason[rule] || (edge.evidence_type === 'direct_hit' ? '\u76f4\u63a5\u547d\u4e2d\u9884\u8b66\u8bc1\u636e' : edge.evidence_type === 'associated_review' ? '\u5173\u8054\u6838\u67e5\u7ebf\u7d22' : `\u89c4\u5219\u8bc1\u636e\uff1a${edge.evidence_type || '\u8d44\u91d1\u6d41\u8f6c'}`) }
  return <div className="graph-canvas"><div className="graph-canvas-toolbar"><span>{nodes.length} 个账户节点 · {edges.length} 条 {graph.data_source || '资金图谱'} 关系 · 当前缩放 {Math.round(zoom * 100)}%</span><span className="graph-toolbar-actions"><button className="text-button" onClick={() => setZoom((value) => Math.min(1.8, value + 0.15))}>放大</button><button className="text-button" onClick={() => setZoom((value) => Math.max(0.55, value - 0.15))}>缩小</button><button className="text-button" onClick={reset}>自动布局</button></span></div><div className="graph-stage interactive-graph" style={{ minHeight: stageHeight }} onPointerDown={beginPan} onPointerMove={movePan} onPointerUp={endPan} onPointerLeave={endPan} onWheel={(event) => { event.preventDefault(); setZoom((value) => Math.max(0.55, Math.min(1.8, value + (event.deltaY < 0 ? 0.08 : -0.08)))) }}><div className="graph-world" style={{ width: stageWidth, height: stageHeight, transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}><svg className="graph-links" viewBox={`0 0 ${stageWidth} ${stageHeight}`}>{edges.map((edge, index) => { const source = positions[edge.source]; const target = positions[edge.target]; if (!source || !target) return null; const isAlert = edge.evidence_type === 'direct_hit' || edge.priority === 'HIGH' || edge.evidence_type === 'rapid_movement'; return <g key={`${edge.transaction_id || index}`} className={`graph-link ${isAlert ? 'alert' : ''} ${edge.evidence_type === 'associated_review' ? 'related' : ''}`} onClick={(event) => { event.stopPropagation(); setSelectedEdge(edge); setSelected(null) }}><line className="graph-link-hit" x1={source.x} y1={source.y} x2={target.x} y2={target.y} /><line x1={source.x} y1={source.y} x2={target.x} y2={target.y} /><title>{reason(edge)} · {edge.transaction_id || '资金关系'}</title></g> })}</svg>{nodes.map((node) => { const position = positions[node.account_id] || { x: stageWidth / 2, y: stageHeight / 2 }; const isDirect = node.account_id === directAccount || node.evidence_type === 'direct_hit'; const isSelected = selected === node.account_id; return <button key={node.account_id} className={`graph-node draggable ${isDirect ? 'direct' : 'related'} ${isSelected ? 'selected' : ''}`} style={{ left: position.x, top: position.y }} onClick={(event) => { event.stopPropagation(); setSelected(node.account_id); setSelectedEdge(null) }} onPointerDown={(event) => beginNodeDrag(node.account_id, event)} onPointerMove={(event) => moveNode(node.account_id, event)} onPointerUp={endNodeDrag}><Graph size={15} /><b>{node.account_id.split('::').pop()}</b><small>{isDirect ? '预警风险账户' : '关联账户'}</small></button> })}</div>{(selected || selectedEdge) && <div className="graph-selection" onPointerDown={(event) => event.stopPropagation()}>{selected && <><b>预警关联账户</b><span>{selected}</span><small>{nodeMap[selected]?.evidence_type || 'account'} · 该节点参与当前资金网络</small></>}{selectedEdge && <><b className="alert-reason">{reason(selectedEdge)}</b><span>{selectedEdge.source} → {selectedEdge.target}</span><small>{selectedEdge.transaction_id || '关系'} · {selectedEdge.amount ? `${selectedEdge.amount} ${selectedEdge.currency || ''}` : '金额见原始交易证据'}</small></>}<button className="secondary-button" onClick={() => { setSelected(null); setSelectedEdge(null) }}>关闭详情</button></div>}</div></div>
}

function seedGraphPositions(nodes, width, height) { return Object.fromEntries(nodes.map((node, index) => { const angle = index * 2.39996; const radius = 80 + (index % 5) * 42; return [node.account_id, { x: width / 2 + Math.cos(angle) * radius, y: height / 2 + Math.sin(angle) * radius }] })) }
function ReviewQueue({ data, onSelect }) { const items = Array.isArray(data) ? data : []; return <div className="page-panel panel"><h2>待审核案件 <small>{items.length}</small></h2>{items.length ? items.map((item) => <button className="data-row" key={item.alert_id} onClick={() => onSelect(item.alert_id)}><span><b>{item.alert_id}</b><small>{item.account_id}</small></span><strong className="risk-number">{item.risk_score}</strong><span>{item.status}</span><ArrowRight size={16} /></button>) : <EmptyPanel text={data?.error || '暂无待审核案件'} />}</div> }
function QualityModePanel() {
  const [mode, setMode] = useState('balanced'); const [result, setResult] = useState(null)
  useEffect(() => { safeApi(`/evaluation/metrics?quality_mode=${mode}`).then((response) => setResult(response.ok ? response.data : { error: true })) }, [mode])
  const overall = result?.overall || {}; const pct = (value) => value == null ? '—' : `${(value * 100).toFixed(2)}%`
  return <section className="page-panel panel quality-mode-panel"><div className="monitoring-section-head"><div><h2>评估模式</h2><p>切换后重新运行对应模式的离线指标</p></div><div className="quality-mode-switch"><button className={mode === 'balanced' ? 'selected' : ''} onClick={() => setMode('balanced')}>平衡模式</button><button className={mode === 'precision80' ? 'selected' : ''} onClick={() => setMode('precision80')}>高精度模式</button></div></div><div className="metric-grid mode-metric-grid">{[['Precision', pct(overall.precision)], ['Recall', pct(overall.recall)], ['F1', pct(overall.f1)], ['TP / FP / FN', overall.tp == null ? '—' : `${overall.tp} / ${overall.fp} / ${overall.fn}`]].map(([label, value]) => <div className="metric-card quality-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div></section>
}

function IndustryBenchmarkPanel() {
  const rows = [['交易监控误报率', '85%–95%，部分机构接近 100%', 'Capgemini KYC/AML 基准研究、2026 行业基准报告'], ['预警最终转化为可疑交易报告（SAR）的比例', '1%–5%', '监管报送基准'], ['每条预警调查耗时', '20–60 分钟', '行业基准'], ['大行日均预警量', '10,000+ 条', '行业基准']]
  return <section className="page-panel panel industry-benchmark"><div className="monitoring-section-head"><div><h2>生产环境的真实水平（重点）</h2><p>行业参考基准，用于理解指标口径，不代表本项目实测结果</p></div><span className="benchmark-badge">REFERENCE</span></div><div className="benchmark-table"><div className="benchmark-row benchmark-header"><span>指标</span><span>行业平均水平</span><span>来源</span></div>{rows.map((row) => <div className="benchmark-row" key={row[0]}><span>{row[0]}</span><b>{row[1]}</b><small>{row[2]}</small></div>)}</div><p className="benchmark-note">翻译成 Precision 口径：真实生产环境的 AML 系统 Precision 大约只有 5%–15%，也就是审核人员看 10 条预警，约 8–9 条可能是误报。</p></section>
}

function MonitoringPage({ data }) {
  const [iteration, setIteration] = useState(data?.iteration || null)
  const [iterationBusy, setIterationBusy] = useState(false)
  const [iterationMessage, setIterationMessage] = useState('')
  const [qualityMode, setQualityMode] = useState(data?.evaluation?.quality_mode || 'balanced')
  const [qualityEvaluation, setQualityEvaluation] = useState(data?.evaluation || {})
  useEffect(() => setIteration(data?.iteration || null), [data?.iteration])
  useEffect(() => setQualityEvaluation(data?.evaluation || {}), [data?.evaluation])
  useEffect(() => { safeApi(`/evaluation/metrics?quality_mode=${qualityMode}`).then((result) => { if (result.ok) setQualityEvaluation(result.data) }) }, [qualityMode])
  const review = data?.review || {}; const evaluation = qualityEvaluation; const overall = evaluation.overall || {}; const rules = evaluation.rules || {}
  const fallback = data?.error ? '接口异常' : '加载中…'; const pct = (value) => value == null ? fallback : `${(value * 100).toFixed(2)}%`
  const operational = [['预警总数', data?.rules?.total_alert_cases ?? data?.alerts?.total ?? data?.alert_count], ['待审核案件', review.pending_count], ['已确认', review.confirmed_count], ['已驳回', review.rejected_count]]
  const quality = [['Precision', pct(overall.precision)], ['Recall', pct(overall.recall)], ['F1', pct(overall.f1)], ['TP / FP / FN', overall.tp == null ? fallback : `${overall.tp} / ${overall.fp} / ${overall.fn}`]]
  const signals = iteration?.latest_proposal?.signals || []
  const signalClass = (level) => level === 'RED' ? 'iteration-signal red' : level === 'YELLOW' ? 'iteration-signal yellow' : 'iteration-signal green'
  async function runIteration() {
    if (iterationBusy) return
    setIterationBusy(true); setIterationMessage('正在采集监控指标、运行离线评估并生成提案…')
    const result = await safeApi('/iteration/run', { method: 'POST' })
    if (!result.ok) setIterationMessage(`运行失败：${result.error.message}`)
    else {
      setIteration({ ...(iteration || {}), snapshot: result.data.snapshot, latest_proposal: { run_id: result.data.run_id, created_at: result.data.snapshot.snapshot_at, signals: result.data.signals, evaluation: result.data.evaluation, proposal_path: result.data.proposal_path }, proposal_count: (iteration?.proposal_count || 0) + 1, signals_summary: { red: result.data.signals.filter((item) => item.level === 'RED').length, yellow: result.data.signals.filter((item) => item.level === 'YELLOW').length, total: result.data.signals.length } })
      setIterationMessage('诊断完成，已生成待人工审批的迭代提案。')
    }
    setIterationBusy(false)
  }
  return <><div className="metric-grid monitoring-grid">{operational.map(([label, value]) => <div className="metric-card panel" key={label}><span>{label}</span><strong>{value ?? fallback}</strong></div>)}</div><section className="page-panel panel iteration-panel"><div className="monitoring-section-head"><div><span className="eyebrow">SELF-ITERATION</span><h2>自迭代中心</h2><p>机器监测、机器诊断、机器提案；规则和模型变更保留人工审批闸门。</p></div><button className="primary-button" onClick={runIteration} disabled={iterationBusy}><Sparkle size={16} />{iterationBusy ? '诊断中…' : '运行一轮诊断'}</button></div><div className="iteration-flow"><span className="iteration-step active">① 监控</span><ArrowRight size={14} /><span className="iteration-step active">② 评估</span><ArrowRight size={14} /><span className="iteration-step active">③ 诊断</span><ArrowRight size={14} /><span className="iteration-step active">④ 提案</span><ArrowRight size={14} /><span className="iteration-step gated">⑤ 人工审批</span></div>{iterationMessage && <div className="iteration-message">{iterationMessage}</div>}<div className="metric-grid iteration-metrics"><div className="metric-card"><span>当前阶段</span><strong>{iteration?.stage_label || '尚未运行'}</strong></div><div className="metric-card"><span>红线信号</span><strong className="iteration-number red-text">{iteration?.signals_summary?.red ?? '—'}</strong></div><div className="metric-card"><span>黄线信号</span><strong className="iteration-number yellow-text">{iteration?.signals_summary?.yellow ?? '—'}</strong></div><div className="metric-card"><span>提案数量</span><strong className="iteration-number">{iteration?.proposal_count ?? '—'}</strong></div></div>{iteration?.latest_proposal ? <div className="iteration-detail"><div className="iteration-detail-head"><b>最新提案 · {iteration.latest_proposal.run_id}</b><span className="proposal-status">待人工审批</span></div><p>{iteration.latest_proposal.created_at || '时间未知'} · 自动发布：禁止</p><div className="iteration-signals">{signals.length ? signals.map((item, index) => <div className={signalClass(item.level)} key={`${item.code}-${index}`}><b>{item.level}</b><span>{item.code}</span><small>{item.message}</small></div>) : <div className={signalClass('GREEN')}><b>GREEN</b><span>ALL_GREEN</span><small>当前指标未触发 SOP 黄线或红线。</small></div>}</div></div> : <EmptyPanel text="尚未生成自迭代提案，点击“运行一轮诊断”开始。" />}</section><section className="page-panel panel monitoring-quality"><div className="monitoring-section-head"><div><h2>规则质量评估</h2><p>离线标签评估，不进入规则推理链路</p></div><span className="snapshot-label">{data?.snapshot_at || ''}</span></div><div className="metric-grid monitoring-quality-grid">{quality.map(([label, value]) => <div className="metric-card quality-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>{evaluation.warning && <div className="monitoring-warning">评估暂不可用：{evaluation.warning}</div>}<div className="rule-quality-table"><div className="rule-quality-row rule-quality-header"><span>规则</span><span>Precision</span><span>Recall</span><span>F1</span><span>TP / FP / FN</span></div>{Object.entries(rules).map(([name, metric]) => <div className="rule-quality-row" key={name}><b>{name}</b><span>{pct(metric.precision)}</span><span>{pct(metric.recall)}</span><span>{pct(metric.f1)}</span><span>{metric.tp} / {metric.fp} / {metric.fn}</span></div>)}</div></section></>
}

function OverlayPanel({ kind, reviewer, authenticated, loginName, loginPassword, loginError, setLoginName, setLoginPassword, onClose, onLogin, onLogout }) {
  if (kind === 'notifications') return <NotificationsPanel onClose={onClose} />
  if (kind === 'filter') return null
  if (authenticated) return <div className="floating-panel user-panel"><b>{reviewer}</b><span>PostgreSQL 账号 · 合规调查组</span><button className="secondary-button" onClick={onLogout}>退出登录</button><button className="secondary-button" onClick={onClose}>关闭</button></div>
  return <div className="floating-panel user-panel login-panel" role="dialog" aria-modal="true"><h3>登录工作台</h3><p>账号来自项目 PostgreSQL 用户表，登录后才可提交人工审核。</p><label className="field-label">用户名<input aria-label="登录用户名" value={loginName} onChange={(event) => setLoginName(event.target.value)} autoComplete="username" /></label><label className="field-label">密码<input aria-label="登录密码" type="password" value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') onLogin() }} autoComplete="current-password" /></label>{loginError && <div className="inline-error" role="alert">{loginError}</div>}<button className="primary-button" onClick={onLogin}><UserCircle size={16} />登录</button><button className="secondary-button" onClick={onClose}>取消</button></div>
}

function AgentReply({ result }) {
  const payload = result?.results || result?.tool_data || {}
  const alert = payload.alert || {}
  const explanation = payload.explainability?.risk_explanation || result?.explainability?.risk_explanation || {}
  const response = payload.risk_response || {}
  const reasons = (explanation.reasons || []).slice(0, 4)
  const report = String(result?.report || '').replace(/<think>[\s\S]*?<\/think>/gi, '').trim()
  const judgement = payload.evidence_judgement || result?.evidence_judgement || {}
  const tasks = result?.tasks || []
  const evidence = payload.evidence || []
  return <div className="agent-reply"><div className="agent-reply-head"><div className="agent-avatar"><Sparkle size={16} weight="fill" /></div><div><b>Multi-Agent 协作调查</b><small>并行专家分析 · Evidence Judge 质检 · 人工审核闸门</small></div></div><p className="agent-conclusion">{explanation.conclusion || `案件 ${alert.alert_id || ''} 已完成证据分析。`}</p><div className="agent-summary-grid"><div><span>风险等级</span><strong className="risk-number">{alert.risk_level || '—'} · {alert.risk_score ?? '—'}</strong></div><div><span>证据裁判</span><strong>{judgement.status || '—'}</strong></div><div><span>交易证据</span><strong>{payload.transaction_evidence?.length ?? 0}</strong></div></div>{tasks.length > 0 && <div className="agent-reply-section"><b>任务时间线</b>{tasks.map((task) => <div className="agent-reason" key={task.task_id}><span>{task.agent_name} · {task.task_type}</span><small>{task.status} · {task.started_time || '未开始'} → {task.finished_time || '进行中'}</small></div>)}</div>}{judgement.issues?.length > 0 && <div className="agent-reply-section"><b>质量提醒</b><p className="agent-recommendations">{judgement.issues.join('；')}</p></div>}{evidence.length > 0 && <div className="agent-reply-section"><b>统一证据索引</b>{evidence.slice(0, 8).map((item, index) => <div className="agent-reason" key={`${item.source}-${index}`}><span>{item.source} · {item.description}</span><small>{item.evidence_ids?.length || 0} 条证据 · 可信度 {item.confidence} · {item.degraded ? '降级' : item.data_source}</small></div>)}</div>}{reasons.length > 0 && <div className="agent-reply-section"><b>主要判断依据</b>{reasons.map((item, index) => <div className="agent-reason" key={`${item.reason}-${index}`}><span>{item.reason}</span><small>{item.evidence}</small></div>)}</div>}{response.recommendations?.length > 0 && <div className="agent-reply-section"><b>建议下一步</b><p className="agent-recommendations">{response.recommendations.slice(0, 3).join('；')}</p></div>}{report && <details className="agent-full-report"><summary>查看完整 AI 报告</summary><div>{report}</div></details>}<small className="agent-disclaimer">AI 结论仅作为调查辅助，最终以证据核验和人工审核为准。</small></div>
}

function SettingsPage() {
  const [health, setHealth] = useState('检查中')
  useEffect(() => { safeApi('/health').then((result) => setHealth(result.ok ? '已连接' : '不可用')) }, [])
  return <div className="page-panel panel settings-page"><div className="settings-row"><div><h2>系统状态</h2><p>当前工作台使用真实后端数据，不启用前端演示数据。</p></div><span className={`settings-status ${health === '已连接' ? 'ok' : ''}`}>{health}</span></div><div className="settings-grid"><div><span>数据源</span><strong>PostgreSQL Warehouse</strong></div><div><span>图谱服务</span><strong>Neo4j / PostgreSQL 降级</strong></div><div><span>AI 模型</span><strong>MiniMax-M2.5</strong></div><div><span>登录方式</span><strong>PostgreSQL 账号</strong></div></div><p className="muted-copy">Neo4j 不可用时，资金路径和风险分析会自动使用 PostgreSQL 事实表，并在结果中保留数据源说明。</p></div>
}

function NotificationsPanel({ onClose }) {
  const [metrics, setMetrics] = useState(null)
  useEffect(() => { safeApi('/monitoring/metrics').then((result) => setMetrics(result.ok ? result.data : { error: true })) }, [])
  const pending = metrics?.review?.pending_count
  return <div className="floating-panel notifications-panel"><div><b>通知</b><button aria-label="关闭通知" className="icon-button" onClick={onClose}><X size={16} /></button></div><p>{metrics?.error ? '通知服务暂时不可用。' : pending == null ? '正在读取案件状态…' : pending > 0 ? `当前有 ${pending} 条预警待人工审核。` : '当前没有新的待处理通知。'}</p><button className="secondary-button" onClick={onClose}>关闭</button></div>
}

createRoot(document.getElementById('root')).render(<App />)
