import { useEffect, useState } from 'react'
import { analyzeJobUrl, getDashboardStats, getHistory, getHistoryItem, getSession, login, logout, predictJob, register } from './services/api'
import './App.css'
import './AppExtension.css'

const blankListing = { title: '', company_name: '', location: '', salary_range: '', company_profile: '', description: '', requirements: '', benefits: '', employment_type: '', required_experience: '', required_education: '', industry: '', function: '', department: '', telecommuting: '', has_company_logo: '', has_questions: '' }

function Shield({ small = false }) { return <span className={`shield ${small ? 'shield-small' : ''}`} aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M12 3 19 6v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/><path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg></span> }
function ResultBadge({ percent }) { const tone = percent >= 75 ? 'high' : percent >= 40 ? 'medium' : 'low'; return <div className={`score-badge ${tone}`}><strong>{percent}%</strong><span>fake likelihood</span></div> }

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('clearhire-theme') || 'light'), [selected, setSelected] = useState(null), [listing, setListing] = useState(blankListing), [result, setResult] = useState(null), [analyzing, setAnalyzing] = useState(false), [notice, setNotice] = useState(''), [view, setView] = useState('feed'), [user, setUser] = useState(null), [authMode, setAuthMode] = useState(''), [authInput, setAuthInput] = useState({ email: '', password: '' }), [historyItems, setHistoryItems] = useState([]), [stats, setStats] = useState(null), [busy, setBusy] = useState(false), [poster, setPoster] = useState(null), [posterPreview, setPosterPreview] = useState(''), [ocrState, setOcrState] = useState(''), [ocrBusy, setOcrBusy] = useState(false), [ocrProgress, setOcrProgress] = useState(0), [postUrl, setPostUrl] = useState('')
  useEffect(() => { localStorage.setItem('clearhire-theme', theme) }, [theme])
  useEffect(() => { getSession().then(data => setUser(data.user)).catch(() => {}) }, [])
  useEffect(() => () => { if (posterPreview) URL.revokeObjectURL(posterPreview) }, [posterPreview])
  useEffect(() => {
    if (!user || view === 'feed') return
    if (view === 'history') getHistory().then(setHistoryItems).catch(error => setNotice(error.message))
    if (view === 'dashboard') getDashboardStats().then(setStats).catch(error => setNotice(error.message))
  }, [view, user])
  async function analyzeListing(event) {
    event.preventDefault(); setAnalyzing(true); setNotice(''); setResult(null)
    try { setResult(await predictJob(listing)); setListing(blankListing) }
    catch (error) { setNotice(error.message) }
    finally { setAnalyzing(false) }
  }
  function choosePoster(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) { setNotice('Choose an image file such as PNG, JPG, or WebP.'); return }
    if (file.size > 8 * 1024 * 1024) { setNotice('Poster images must be 8 MB or smaller.'); return }
    setPoster(file); setPosterPreview(URL.createObjectURL(file)); setOcrState(''); setOcrProgress(0); setNotice('')
  }
  async function extractPosterText() {
    if (!poster) return
    setOcrState('Loading OCR…'); setOcrBusy(true); setOcrProgress(0); setNotice('')
    let worker
    try {
      const { createWorker } = await import('tesseract.js')
      worker = await createWorker('eng', 1, { logger: message => { if (message.status === 'recognizing text') setOcrProgress(Math.round((message.progress || 0) * 100)); setOcrState(message.status || 'Reading poster…') } })
      const { data } = await worker.recognize(poster)
      const text = data.text.trim()
      if (text.length < 20) throw new Error('I could not read enough text. Try a sharper image or paste the job description.')
      setListing(current => ({ ...current, description: current.description ? `${current.description}\n\n${text}` : text }))
      setOcrState('Text extracted. Review it below, then run the check.')
    } catch (error) { setOcrState(''); setNotice(error.message || 'Poster text extraction failed. You can still paste the listing text manually.') }
    finally { if (worker) { try { await worker.terminate() } catch { /* worker cleanup should not hide OCR results */ } } setOcrProgress(0); setOcrBusy(false) }
  }
  async function analyzeUrl(event) {
    event.preventDefault(); setAnalyzing(true); setNotice(''); setResult(null)
    try {
      const response = await analyzeJobUrl(postUrl.trim())
      setResult(response)
      const source = response.source_listing || {}
      setListing(current => ({ ...current, title: source.title || current.title, company_name: source.company_name || current.company_name, location: source.location || current.location, description: source.description || current.description }))
      setNotice('Job page extracted and checked. Review the result below.')
    } catch (error) { setNotice(error.message) }
    finally { setAnalyzing(false) }
  }
  function changeField(key, value) { setListing(current => ({ ...current, [key]: value })) }
  async function submitAuth(event) {
    event.preventDefault(); setBusy(true); setNotice('')
    try { const data = authMode === 'register' ? await register(authInput) : await login(authInput); setUser(data.user); setAuthMode(''); setAuthInput({ email: '', password: '' }); setNotice(authMode === 'register' ? 'Account created. Your future analyses will be saved here.' : 'Signed in.') }
    catch (error) { setNotice(error.message) } finally { setBusy(false) }
  }
  async function openHistory(item) {
    try { const detail = await getHistoryItem(item.id); setSelected({ ...detail, score: Math.round(detail.fake_probability * 100), company: detail.company_name || 'Submitted job post', title: detail.job_title, description: detail.input?.description || '', location: detail.input?.location || 'Not provided', salary: detail.input?.salary_range || 'Not provided', url: detail.input?.source_url, prediction: detail.prediction, explanations: detail.explanations }) }
    catch (error) { setNotice(error.message) }
  }
  const heading = view === 'dashboard' ? 'Dashboard' : view === 'history' ? 'Prediction history' : 'Check a post'
  const hasListing = listing.title.trim() || listing.description.trim()
  return <div className="app-shell" data-theme={theme}>
    <aside className="sidebar"><a className="brand" href="#top" onClick={() => setView('feed')}><span className="brand-icon"><Shield small /></span><span>clearhire<span className="brand-dot">.</span></span></a><div className="side-label">WORKSPACE</div><nav className="side-nav" aria-label="Main navigation"><button className={`nav-link ${view === 'feed' ? 'active' : ''}`} onClick={() => setView('feed')}><span className="nav-icon">✳</span>Check a post</button><button className={`nav-link ${view === 'dashboard' ? 'active' : ''}`} onClick={() => user ? setView('dashboard') : setAuthMode('login')}><span className="nav-icon">▥</span>Dashboard</button><button className={`nav-link ${view === 'history' ? 'active' : ''}`} onClick={() => user ? setView('history') : setAuthMode('login')}><span className="nav-icon">◷</span>Analysis history</button></nav><div className="side-bottom"><div className="trust-card"><div className="trust-mark"><Shield small /></div><strong>Make your next move<br/>with confidence.</strong><p>Every listing checked.<br/>Every red flag explained.</p><span>HOW IT WORKS <span>↗</span></span></div><button className="profile" onClick={() => user ? logout().then(() => { setUser(null); setView('feed') }) : setAuthMode('login')}><span className="avatar">{user?.email?.slice(0, 2).toUpperCase() || 'JD'}</span><span><strong>{user?.email || 'Guest user'}</strong><small>{user ? 'Sign out' : 'Sign in to save history'}</small></span><span className="profile-more">···</span></button></div></aside>
    <main className="main-content" id="top"><header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <strong>{heading}</strong></div><div className="top-actions"><span className="live-dot"></span><span className="live-label">Poster · text · URL checks</span><button className="theme-toggle" type="button" aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>{theme === 'light' ? '☾' : '☀'}<span>{theme === 'light' ? 'Dark' : 'Light'}</span></button><button className="account-button" onClick={() => user ? logout().then(() => { setUser(null); setView('feed') }) : setAuthMode('login')}>{user ? 'Sign out' : 'Sign in'}</button></div></header><div className="content-wrap">
      {view === 'feed' && <>
      <section className="welcome-row"><div><div className="eyebrow"><span className="sparkle">✳</span> YOUR JOB SEARCH, SAFER</div><h1>Find work worth<br/><em>your trust.</em></h1><p className="welcome-copy">Check a job poster, public post link, or copied description<br className="desktop-break"/> for common fraud signals.</p></div><div className="scan-art" aria-hidden="true"><div className="orbit orbit-outer"></div><div className="orbit orbit-inner"></div><div className="scan-glow"></div><div className="scan-shield"><Shield /></div><span className="float-dot dot-one"></span><span className="float-dot dot-two"></span><span className="float-dot dot-three"></span><span className="scan-spark">✳</span><span className="scan-line"></span></div></section>
      <form className="analyze-card" onSubmit={analyzeListing}>
        <div className="analyze-symbol"><span>✳</span></div>
        <div className="analyze-body">
          <div className="analyze-heading"><div><h2>Check a suspicious job post</h2><p>Upload a poster, paste a post URL, or enter the text.</p></div><span className="free-pill">ML CHECK <span>✳</span></span></div>
          <div className="poster-upload-panel">
            <label className="field-label poster-picker">Upload a job poster<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={choosePoster}/><small>PNG, JPG, WebP or GIF · up to 8 MB</small></label>
            {posterPreview && <div className="poster-preview"><img src={posterPreview} alt="Preview of uploaded job poster"/><div><strong>{poster.name}</strong><span>Image stays in your browser while text is extracted.</span><button type="button" className="text-button" onClick={extractPosterText} disabled={ocrBusy}>{ocrBusy ? `${ocrState}${ocrProgress ? ` · ${ocrProgress}%` : ''}` : ocrState || 'Extract text from poster'}</button><button type="button" className="text-button remove-poster" onClick={() => {setPoster(null);setPosterPreview('');setOcrState('')}} disabled={ocrBusy}>Remove image</button></div></div>}
          </div>
          <label className="field-label">Job post text<textarea aria-label="Job description" value={listing.description} onChange={e => changeField('description', e.target.value)} placeholder="Paste the complete job posting here, or extract it from an image above..." rows="6" /></label>
          <details className="optional-fields"><summary>Add structured listing details</summary><div className="field-grid">{[['title','Job title'],['company_name','Company'],['location','Location'],['salary_range','Salary range'],['company_profile','Company profile'],['requirements','Requirements'],['benefits','Benefits'],['employment_type','Employment type'],['required_experience','Experience'],['required_education','Education'],['industry','Industry'],['function','Job function']].map(([key,label]) => <label className="field-label" key={key}>{label}<input value={listing[key]} onChange={e => changeField(key,e.target.value)} /></label>)}</div></details>
          <div className="form-actions"><span className="privacy-note"><span>⌑</span> {user ? 'Your analyses are saved to your private history.' : 'Sign in to save a private analysis history.'}</span><button type="submit" disabled={analyzing || !hasListing}>{analyzing ? 'Checking…' : 'Analyze job post'}<span>→</span></button></div>
          {result && <section className="prediction-result" aria-live="polite"><div className="result-title"><ResultBadge percent={result.fake_percent}/><span className={`result-label ${result.prediction.toLowerCase()}`}>{result.prediction === 'FAKE' ? 'Potentially fraudulent' : 'More likely legitimate'}</span><span>{Math.round(result.confidence * 100)}% confidence · {result.risk_level.toLowerCase()} risk</span></div>{result.source_url && <p>Checked from <a href={result.source_url} target="_blank" rel="noreferrer">the submitted job page ↗</a></p>}<p>{result.notice}</p><ul>{result.explanations.map((reason, i) => <li key={i}>{reason}</li>)}</ul>{!user && <button type="button" className="text-button" onClick={() => setAuthMode('register')}>Create an account to save future checks ↗</button>}</section>}
        </div>
      </form>
      <form className="url-checker" onSubmit={analyzeUrl}><div><div className="section-kicker">CHECK A PUBLIC LISTING</div><h2>Analyze by post URL</h2><p>We’ll read the public page and score its job-post text. Sign-in-only pages may not work.</p></div><div className="url-checker-row"><input type="url" required value={postUrl} onChange={event => setPostUrl(event.target.value)} placeholder="https://example.com/jobs/role" aria-label="Public job post URL"/><button type="submit" disabled={analyzing || !postUrl.trim()}>{analyzing ? 'Checking page…' : 'Check URL'}<span>→</span></button></div><small>Only public HTTPS pages are fetched. The page text is used for analysis.</small></form>
      {notice && <div className="notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}
      </>}
      {view === 'dashboard' && <section className="account-page"><div className="eyebrow">YOUR ACTIVITY</div><h1>Analysis dashboard</h1><p className="welcome-copy">A summary of job listings you have checked.</p>{stats ? <div className="stats-grid">{[['Total checked',stats.total],['Potentially fake',stats.fake],['Likely real',stats.real],['High risk',stats.high_risk]].map(([label,value])=><article className="stat-card" key={label}><span>{label}</span><strong>{value}</strong></article>)}</div> : <p>Loading your dashboard…</p>}<button className="action-button" onClick={() => setView('history')}>View analysis history →</button></section>}
      {view === 'history' && <section className="account-page"><div className="eyebrow">SAVED CHECKS</div><h1>Analysis history</h1><p className="welcome-copy">Your recent checks are private to this account.</p>{historyItems.length ? <div className="history-list">{historyItems.map(item=><button className="history-row" key={item.id} onClick={() => openHistory(item)}><span><strong>{item.job_title || 'Untitled job'}</strong><small>{item.company_name || 'Company not provided'} · {new Date(`${item.created_at}Z`).toLocaleString()}</small></span><ResultBadge percent={Math.round(item.fake_probability*100)}/><span className="history-confidence">{item.risk_level.toLowerCase()} risk</span></button>)}</div> : <div className="empty-state">No saved analyses yet. Run a check and sign in to keep it in your history.</div>}</section>}
      <footer className="page-footer"><span>© 2026 Clearhire</span><span><a href="#top">Privacy</a><a href="#top">How scoring works</a><a href="#top">Help center ↗</a></span></footer>
    </div></main>
    {selected && <div className="modal-backdrop" role="presentation" onClick={() => setSelected(null)}><section className="detail-modal" role="dialog" aria-modal="true" aria-label="Job listing details" onClick={e => e.stopPropagation()}><button className="modal-close" onClick={() => setSelected(null)} aria-label="Close">×</button><div className={`company-mark modal-mark ${selected.color || 'blue'}`}>{selected.mark || '✳'}</div><div className="job-company">{selected.company || selected.company_name || 'Company not provided'}</div><h2>{selected.title || selected.job_title}</h2><p className="modal-meta">{selected.location} · {selected.salary} · {selected.source || 'Submitted post'}</p><div className="modal-score">{selected.prediction ? <ResultBadge percent={selected.score}/> : <ResultBadge percent={selected.score ?? 0}/>}<div><strong>{selected.prediction ? `${selected.prediction} · ${selected.risk_level?.toLowerCase()} risk` : 'Trust check'}</strong><p>{selected.signal || selected.explanations?.join(' · ')}</p></div></div><h3>About this listing</h3><p className="description">{selected.description || 'No description stored.'}</p>{selected.url && <a className="apply-link" href={selected.url} target="_blank" rel="noreferrer">Open original posting ↗</a>}<div className="modal-footnote"><Shield small/> Model results are estimates, not guarantees. Verify employers before sharing personal information.</div></section></div>}
    {authMode && <div className="modal-backdrop" onClick={() => setAuthMode('')}><section className="detail-modal auth-modal" role="dialog" aria-modal="true" aria-label="Account access" onClick={event => event.stopPropagation()}><button className="modal-close" onClick={() => setAuthMode('')} aria-label="Close">×</button><div className="eyebrow">CLEARHIRE ACCOUNT</div><h2>{authMode === 'register' ? 'Create your account' : 'Welcome back'}</h2><p>Save your checks and review your analysis history.</p><form onSubmit={submitAuth}><label className="field-label">Email<input type="email" required autoComplete="email" value={authInput.email} onChange={event => setAuthInput({...authInput,email:event.target.value})}/></label><label className="field-label">Password<input type="password" minLength="10" required autoComplete={authMode==='register'?'new-password':'current-password'} value={authInput.password} onChange={event => setAuthInput({...authInput,password:event.target.value})}/></label><button className="action-button" disabled={busy}>{busy ? 'Please wait…' : authMode === 'register' ? 'Create account' : 'Sign in'}</button></form><button className="text-button" onClick={() => setAuthMode(authMode==='register'?'login':'register')}>{authMode==='register'?'Already have an account? Sign in':'New here? Create an account'}</button>{notice && <p role="status">{notice}</p>}</section></div>}
  </div>
}
export default App
