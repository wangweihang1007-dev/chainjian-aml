const base = (process.env.SMOKE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const frontend = (process.env.SMOKE_FRONTEND_URL || 'http://127.0.0.1:4173').replace(/\/$/, '')
const strict = process.env.SMOKE_STRICT !== 'false'

async function request(url, options) {
  const response = await fetch(url, options)
  let body = null
  try { body = await response.json() } catch { /* status-only response */ }
  return { response, body }
}

const checks = []
function check(name, pass, detail = '') {
  checks.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`)
}

const page = await fetch(frontend)
check('页面启动', page.ok, `${page.status} ${frontend}`)
const health = await request(`${base}/health`)
check('后端健康检查', health.response.ok && health.body?.status === 'ok', `${health.response.status}`)
if (!health.response.ok) process.exit(1)

const alerts = await request(`${base}/alerts`)
const alertId = process.env.SMOKE_ALERT_ID || alerts.body?.[0]?.alert_id
check('预警列表', alerts.response.ok && Array.isArray(alerts.body) && Boolean(alertId), `${alerts.response.status}, alert=${alertId || 'none'}`)
if (!alertId) process.exit(1)

const encoded = encodeURIComponent(alertId)
const evidence = await request(`${base}/alerts/${encoded}/explainability`)
const counterfactual = await request(`${base}/alerts/${encoded}/counterfactual`)
const report = await request(`${base}/reports/${encoded}`)
check('证据链', evidence.response.ok, `${evidence.response.status}`)
check('反事实分析', counterfactual.response.ok, `${counterfactual.response.status}`)
check('报告生成', report.response.ok, `${report.response.status}`)

const review = await request(`${base}/alerts/${encoded}/review`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ action: 'CONFIRM', reviewer: '', comment: '' }),
})
check('人工审核接口校验', review.response.status === 400, `${review.response.status} expected 400 for missing required fields`)

const degraded = [evidence, counterfactual, report].filter(({ response }) => response.status === 503).length
if (degraded) console.warn(`WARN ${degraded} 个依赖图谱/Agent 的接口处于降级状态；设置 SMOKE_STRICT=true 可将其视为失败。`)
if (strict && checks.some((item) => !item.pass)) process.exit(1)
