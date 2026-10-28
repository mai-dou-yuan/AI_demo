'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { ArrowDownToLine, ArrowRight, ArrowUp, BookOpen, BrainCircuit, Check, CheckCheck, ChevronRight, CircleAlert, CircleCheck, Clock3, FileText, FolderOpen, Globe2, Layers3, ListTodo, LoaderCircle, Mail, Menu, MessageSquare, PanelRightClose, PanelRightOpen, Paperclip, Pencil, Plus, Presentation, RefreshCw, Search, ShieldCheck, Sparkles, Trash2, Upload, Users, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Markdown } from './markdown';
import PersonalWorkspace from './personal-workspace';
import { api, authenticatedFetch, safeHref, type Artifact, type BrainFile, type Conversation, type Health, type SmtpSettings, type Job, type Meeting, type Memory, type Message, type Source, type Task } from '@/lib/api';

const sections = [
  { id: 'chat', label: '对话', icon: MessageSquare, description: '把问题交给你的外脑' },
  { id: 'knowledge', label: '知识库', icon: BookOpen, description: '让每一份资料，都成为可用的知识' },
  { id: 'meetings', label: '会议', icon: Users, description: '从讨论中提炼共识，让行动有迹可循' },
  { id: 'memories', label: '长期记忆', icon: BrainCircuit, description: '重要的事，跨越每一次对话' },
  { id: 'tasks', label: '待办事项', icon: ListTodo, description: '把潜在风险，变成明确的下一步' },
  { id: 'slides', label: '演示文稿', icon: Presentation, description: '从一个想法，到一份完整的表达' },
];
const examples = [
  { icon: BookOpen, tag: '知识问答', title: '读懂一份复杂的资料', text: '上传 PDF，提取重点、回答问题并追溯原文。', prompt: '' },
  { icon: Users, tag: '会议洞察', title: '让讨论真正落到行动', text: '上传会议 TXT，发现风险，创建待办并邮件提醒。', prompt: '' },
  { icon: Globe2, tag: '实时搜索', title: '跟上正在发生的变化', text: '搜索最新信息，结合可靠来源形成你的判断。', prompt: '搜索近期 AI Agent 在企业办公中的应用进展，附上来源。' },
  { icon: Presentation, tag: '内容创作', title: '把想法变成演示文稿', text: '给出主题与受众，生成可下载的 PowerPoint。', prompt: '生成一份 6 页的 AI Agent 应用介绍 PPT，受众是企业管理者。' },
];
const labels: Record<string, string> = { queued: '排队中', running: '处理中', succeeded: '已完成', failed: '失败', processing: '解析中', ready: '可用', pending: '待处理', sent: '已发送', sending: '发送中', unknown: '结果待核对', open: '待跟进', done: '已完成', high: '高风险', medium: '中风险', low: '低风险' };
const errorText = (e: unknown) => e instanceof Error ? e.message : '操作失败，请重试';
function Badge({ value }: { value: string }) { return <span className={`badge badge-${value}`}>{labels[value] || value}</span>; }
function Empty({ title, detail }: { title: string; detail: string }) { return <div className="empty-state"><span><FolderOpen size={29} strokeWidth={1.5} /></span><h3>{title}</h3><p>{detail}</p></div>; }
function FileCard({ artifact, onDelete, disabled }: { artifact: Artifact; onDelete?: () => void; disabled?: boolean }) { return <div className="artifact-row"><a className="download-card" href={`/api/artifacts/${artifact.id}/download`}><span className="file-icon purple"><Presentation size={22} /></span><span><strong>{artifact.filename}</strong><small>PowerPoint · 点击下载</small></span><ArrowDownToLine size={18} /></a>{onDelete && <Button variant="destructive" size="sm" disabled={disabled} onClick={onDelete}><Trash2 size={13} />删除</Button>}</div>; }

type WorkspaceProps = { username: string; accountBusy: boolean; accountError?: string; onChangePassword: () => void; onLogout: () => void };

export default function Workspace({ username, accountBusy, accountError, onChangePassword, onLogout }: WorkspaceProps) {
  const [section, setSection] = useState('chat');
  const [health, setHealth] = useState<Health | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [files, setFiles] = useState<BrainFile[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingQuery, setMeetingQuery] = useState('');
  const [meetingStatus, setMeetingStatus] = useState('all');
  const [selectedMeeting, setSelectedMeeting] = useState('');
  const [memories, setMemories] = useState<Memory[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false); const [status, setStatus] = useState('');
  const [input, setInput] = useState(''); const [search, setSearch] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [contextOpen, setContextOpen] = useState(true); const [menuOpen, setMenuOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false); const [filter, setFilter] = useState('');
  const [mailOpen, setMailOpen] = useState(false);
  const [mailError, setMailError] = useState('');
  const [mailSettings, setMailSettings] = useState<SmtpSettings | null>(null);
  const [mailPassword, setMailPassword] = useState('');
  const [mailRecipients, setMailRecipients] = useState('');
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [memoryError, setMemoryError] = useState('');
  const [memoryDraft, setMemoryDraft] = useState({ summary: '', person: '', time_text: '', location: '', topic: '', evidence: '' });
  const [memoryFilters, setMemoryFilters] = useState({ person: '', time: '', location: '', topic: '' });
  const [slideTopic, setSlideTopic] = useState(''); const [pages, setPages] = useState(6);
  const [useKnowledge, setUseKnowledge] = useState(false); const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [rename, setRename] = useState<string | null>(null); const [renameTitle, setRenameTitle] = useState('');
  const uploadRef = useRef<HTMLInputElement>(null); const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null); const controllerRef = useRef<AbortController | null>(null);

  const refresh = useCallback(async (quiet = false) => {
    try {
      const [h, c, f, m, r, t, a, j] = await Promise.all([api<Health>('/health'), api<Conversation[]>('/conversations'), api<BrainFile[]>('/files'), api<Meeting[]>('/meetings'), api<Memory[]>('/memories'), api<Task[]>('/tasks'), api<Artifact[]>('/artifacts'), api<Job[]>('/jobs')]);
      setHealth(h); setConversations(c); setFiles(f); setMeetings(m); setMemories(r); setTasks(t); setArtifacts(a); setJobs(j);
    } catch (e) { if (!quiet) setError(errorText(e) + '。请确认后端已启动。'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refresh(); const timer = setInterval(() => void refresh(true), 5000); return () => clearInterval(timer); }, [refresh]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: busy ? 'instant' : 'smooth' }); }, [messages, busy]);
  useEffect(() => () => controllerRef.current?.abort(), []);

  const sources: Source[] = messages.flatMap(m => m.metadata?.sources || []).filter((s, i, all) => all.findIndex(other => (other.text_url || other.url) === (s.text_url || s.url)) === i).slice(-8);
  const meetingFiles = files.filter(file => file.type === 'txt');
  const visibleMeetingFiles = meetingFiles.filter(file => {
    const meeting = meetings.find(item => item.file_id === file.id);
    const query = meetingQuery.trim().toLocaleLowerCase();
    const text = [file.filename, meeting?.analysis.topic, meeting?.analysis.summary, meeting?.analysis.time, meeting?.analysis.people.join('、')].join(' ').toLocaleLowerCase();
    return (meetingStatus === 'all' || file.status === meetingStatus) && (!query || text.includes(query));
  });
  const shownMeetingFiles = visibleMeetingFiles.filter(file => !selectedMeeting || file.id === selectedMeeting);
  const shownMeetings = meetings.filter(meeting => shownMeetingFiles.some(file => file.id === meeting.file_id));
  const active = sections.find(item => item.id === section)!;
  const openTasks = tasks.filter(t => t.status === 'open');
  function navigate(id: string) { setSection(id); setMenuOpen(false); setFilter(''); }
  async function runAction(key: string, action: () => Promise<unknown>) {
    setActionBusy(key); setError('');
    try { await action(); } catch (e) { setError(errorText(e)); }
    finally { await refresh(true); setActionBusy(null); }
  }
  async function selectConversation(id: string) {
    if (busy) return;
    setActionBusy('history'); setError('');
    try { setMessages(await api<Message[]>(`/conversations/${id}/messages`)); setConversation(id); navigate('chat'); }
    catch (e) { setError(errorText(e)); } finally { setActionBusy(null); }
  }
  function newConversation() { if (busy) return; setConversation(null); setMessages([]); setSelectedFiles([]); setNotice(''); navigate('chat'); }
  async function upload(file: File) {
    setUploading(true); setError('');
    try { const form = new FormData(); form.append('file', file); const result = await api<{ duplicate: boolean }>('/files/upload', { method: 'POST', body: form }); setNotice(result.duplicate ? '该文件已存在，未重复创建任务或发送邮件。' : '上传成功，正在后台解析，请查看最近任务。'); navigate(file.name.toLowerCase().endsWith('.pdf') ? 'knowledge' : 'meetings'); await refresh(true); }
    catch (e) { setError(errorText(e)); } finally { setUploading(false); if (uploadRef.current) uploadRef.current.value = ''; }
  }
  async function reparsePdf(file: BrainFile) {
    await runAction(file.id, async () => {
      await api(`/files/${file.id}/reparse`, { method: 'POST' });
      setSelectedFiles(current => current.filter(id => id !== file.id));
      setNotice('已创建重新解析任务，将更新提取文本和知识索引。');
    });
  }
  async function deletePdf(file: BrainFile) {
    if (!window.confirm(`确定删除「${file.filename}」吗？原 PDF、提取文本、知识索引和该文件的任务记录将被删除。聊天记录保留，但其中的原文链接将无法打开。`)) return;
    await runAction(file.id, async () => {
      await api(`/files/${file.id}`, { method: 'DELETE' });
      setSelectedFiles(current => current.filter(id => id !== file.id));
      setNotice('文档、提取文本与知识索引已删除。');
    });
  }
  async function openMailSettings() {
    await runAction('load-smtp', async () => {
      const config = await api<SmtpSettings>('/settings/smtp');
      setMailSettings({ ...config, smtp_host: config.smtp_host || 'smtp.qq.com', smtp_port: config.smtp_port || 465 });
      setMailRecipients(config.smtp_allowed_recipients.join('\n')); setMailPassword(''); setMailError(''); setMailOpen(true);
    });
  }
  async function saveMailSettings() {
    if (!mailSettings || actionBusy !== null) return;
    setActionBusy('save-smtp'); setMailError('');
    try {
      await api<SmtpSettings>('/settings/smtp', { method: 'PUT', body: JSON.stringify({ ...mailSettings, password_set: undefined, configured: undefined, smtp_password: mailPassword || null, smtp_allowed_recipients: mailRecipients.split(/[\s,，;；]+/).filter(Boolean) }) });
      setMailPassword(''); setMailOpen(false); setNotice('邮件设置已保存并生效；保存不会发送邮件。可在待办上点击重试邮件。'); await refresh(true);
    } catch (e) { setMailError(errorText(e)); }
    finally { setActionBusy(null); }
  }
  async function deleteMeeting(file: BrainFile) {
    if (!window.confirm(`确定删除会议「${file.filename}」吗？将删除原文、分析结果、风险待办、邮件发送记录、该会议提取的长期记忆及其语义索引。聊天历史保留，已发送邮件无法撤回。`)) return;
    await runAction('meeting-' + file.id, async () => {
      await api(`/files/${file.id}`, { method: 'DELETE' });
      setSelectedMeeting(current => current === file.id ? '' : current);
      setNotice('会议及相关分析、待办、记忆和索引已删除。');
    });
  }
  async function deleteTask(task: Task) {
    if (!window.confirm(`确定删除待办「${task.title}」吗？待办及其邮件发送记录将删除，会议原文、摘要和长期记忆保留。已发送邮件无法撤回。`)) return;
    await runAction('delete-task-' + task.id, async () => {
      await api(`/tasks/${task.id}`, { method: 'DELETE' });
      setNotice('待办及其邮件发送记录已删除。');
    });
  }
  async function deleteArtifact(artifact: Artifact) {
    if (!window.confirm(`确定删除「${artifact.filename}」吗？生成的 PPTX 文件和下载记录将删除。聊天历史保留，其中的下载链接将失效。`)) return;
    await runAction('delete-artifact-' + artifact.id, async () => {
      await api(`/artifacts/${artifact.id}`, { method: 'DELETE' });
      setNotice('演示文稿及相关生成记录已删除。');
    });
  }
  async function createMemory() {
    if (actionBusy !== null) return;
    setActionBusy('create-memory'); setMemoryError(''); setError('');
    try {
      const result = await api<{ memory: Memory; warning: string | null }>('/memories', { method: 'POST', body: JSON.stringify(memoryDraft) });
      setNotice(result.warning || '记忆已保存，并已建立语义索引。');
      setMemoryOpen(false); setMemoryDraft({ summary: '', person: '', time_text: '', location: '', topic: '', evidence: '' });
      setFilter(''); setMemoryFilters({ person: '', time: '', location: '', topic: '' });
      await refresh(true);
    } catch (e) { setMemoryError(errorText(e)); }
    finally { setActionBusy(null); }
  }
  async function deleteMemory(memory: Memory) {
    if (!window.confirm(`确定删除这条记忆吗？\n${memory.summary}\n记忆及其语义索引将删除，原始聊天或会议记录保留。`)) return;
    await runAction('memory-' + memory.id, async () => {
      await api(`/memories/${memory.id}`, { method: 'DELETE' });
      setMemories(current => current.filter(item => item.id !== memory.id));
      setNotice('记忆及其语义索引已删除。');
    });
  }
  async function send() {
    const text = input.trim(); if (!text || busy) return;
    setBusy(true); setError(''); setNotice(''); setStatus('正在连接'); setInput('');
    const controller = new AbortController(); controllerRef.current = controller;
    let id = conversation; const draftId = 'draft-' + Date.now(); let finished = false;
    try {
      if (!id) { const created = await api<Conversation>('/conversations', { method: 'POST', body: JSON.stringify({ title: text.slice(0, 28) }) }); id = created.id; setConversation(id); }
      setMessages(current => [...current, { id: 'user-' + Date.now(), role: 'user', content: text }, { id: draftId, role: 'assistant', content: '', metadata: {} }]);
      const response = await authenticatedFetch('/chat/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ conversation_id: id, message: text, file_ids: selectedFiles, search }), signal: controller.signal });
      if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(typeof body?.detail === 'string' ? body.detail : '无法开始对话'); }
      if (!response.body) throw new Error('浏览器不支持流式响应');
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      while (true) {
        const { value, done } = await reader.read(); buffer += decoder.decode(value, { stream: !done });
        const events = buffer.split('\n\n'); buffer = events.pop() || '';
        for (const raw of events) {
          const line = raw.split('\n').find(line => line.startsWith('data: ')); if (!line) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === 'status') setStatus(event.content);
          if (event.type === 'warning') setNotice(event.content);
          if (event.type === 'error') throw new Error(event.content);
          if (event.type === 'done') finished = true;
          if (['delta', 'sources', 'artifact'].includes(event.type)) setMessages(current => current.map(m => m.id !== draftId ? m : { ...m, content: m.content + (event.type === 'delta' ? event.content : ''), metadata: { ...m.metadata, ...(event.type === 'sources' ? { sources: event.sources } : {}), ...(event.type === 'artifact' ? { artifact: event.artifact } : {}) } }));
        }
        if (done) break;
      }
      if (!finished) throw new Error('连接中断，回答未完整生成，请重试');
    } catch (e) { const detail = controller.signal.aborted ? '生成已停止，部分内容可能尚未保存。' : errorText(e); setError(detail); setMessages(current => current.map(m => m.id === draftId ? { ...m, content: m.content || detail, metadata: { ...m.metadata, failed: true } } : m)); }
    finally { setBusy(false); setStatus(''); controllerRef.current = null; await refresh(true); if (finished && id) { try { setMessages(await api<Message[]>(`/conversations/${id}/messages`)); } catch { /* Retain streamed content. */ } } }
  }
  const taskCard = (task: Task) => <article key={task.id} className={`task-card ${task.status === 'done' ? 'task-done' : ''}`}>
    <div className="card-top"><Badge value={task.level} /><Badge value={task.status} /></div><h3>{task.title}</h3><p>{task.description}</p>
    <div className="task-meta"><span><Users size={14} />{task.owner || '责任人未明确'}</span><span><Clock3 size={14} />{task.deadline || '期限未明确'}</span></div>
    <blockquote>{task.evidence}</blockquote><p className="suggestion">建议：{task.suggestion}</p>
    <div className="task-bottom"><span><Mail size={14} /><Badge value={task.email_status} /></span><div>{task.email_status !== 'sent' && <Button variant="ghost" size="sm" disabled={actionBusy === task.id || task.email_status === 'sending'} onClick={() => void runAction(task.id, async () => { const result = await api<Task & { email_errors?: string[] }>(`/tasks/${task.id}/retry-email`, { method: 'POST' }); if (result.email_status !== 'sent') throw new Error(result.email_errors?.join('；') || '邮件发送失败'); })}>重试邮件</Button>}<Button variant="outline" size="sm" disabled={actionBusy === task.id} onClick={() => void runAction(task.id, () => api(`/tasks/${task.id}`, { method: 'PATCH', body: JSON.stringify({ status: task.status === 'done' ? 'open' : 'done' }) }))}>{task.status === 'done' ? '重新打开' : <><Check size={14} />完成</>}</Button><Button variant="destructive" size="sm" disabled={actionBusy !== null || busy || task.email_status === 'sending'} onClick={() => void deleteTask(task)}><Trash2 size={12} />删除</Button></div></div>{task.email_logs?.filter(log => task.email_status !== 'sent' && log.error).map(log => <small className="inline-error" key={log.recipient}>{log.recipient}：{log.error}</small>)}
  </article>;

  return <div className="workspace">
    <input ref={uploadRef} type="file" accept={section === 'meetings' ? '.txt' : section === 'knowledge' ? '.pdf' : '.pdf,.txt'} hidden onChange={event => { const file = event.target.files?.[0]; if (file) void upload(file); }} />
    {menuOpen && <div className="mobile-scrim" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'is-open' : ''}`}>
      <button className="brand" onClick={newConversation}><span className="brand-mark"><BrainCircuit size={24} /></span><strong>Cortex<span>SECOND BRAIN</span></strong></button>
      <button className="new-chat" disabled={busy} onClick={newConversation}><Plus size={17} />新建对话<span>＋</span></button><p className="nav-caption">工作空间</p>
      <nav>{sections.map(item => <button key={item.id} className={section === item.id ? 'active' : ''} onClick={() => navigate(item.id)}><item.icon size={18} strokeWidth={1.7} />{item.label}{item.id === 'tasks' && openTasks.length > 0 && <span className="nav-count">{openTasks.length}</span>}</button>)}</nav>
      <div className="recent-heading"><span>最近对话</span><MessageSquare size={13} /></div><div className="recent-list">{conversations.slice(0, 12).map(item => <div className={`recent-item ${conversation === item.id ? 'selected' : ''}`} key={item.id}><button disabled={busy} onClick={() => void selectConversation(item.id)}><span />{item.title}</button><button className="rename-button" aria-label="重命名会话" onClick={() => { setRename(item.id); setRenameTitle(item.title); }}><Pencil size={12} /></button></div>)}{!conversations.length && <small>你的第一段思考，将从这里开始</small>}</div>
      <div className="sidebar-bottom"><div className="local-note"><ShieldCheck size={17} /><span>你的知识，留在本地<small>会话与文件持久保存在本机</small></span></div><PersonalWorkspace username={username} busy={accountBusy || actionBusy !== null} error={accountError} onChangePassword={onChangePassword} onLogout={onLogout} onSettings={() => setSettingsOpen(true)} onMailSettings={() => { navigate('tasks'); void openMailSettings(); }} /></div>
    </aside>
    <div className="workspace-main"><header className="topbar"><div><button className="icon-button mobile-menu" aria-label="打开导航" onClick={() => setMenuOpen(true)}><Menu size={20} /></button><span className="breadcrumb">工作空间</span><ChevronRight size={13} /><strong>{active.label}</strong></div><div><span className={`connection ${health ? 'connected' : ''}`}><i />{health ? '本地服务已连接' : '等待连接后端'}</span><button className="icon-button" aria-label="刷新数据" onClick={() => void refresh()}><RefreshCw size={16} /></button><button className="icon-button" aria-label="切换上下文面板" onClick={() => setContextOpen(!contextOpen)}>{contextOpen ? <PanelRightClose size={18} /> : <PanelRightOpen size={18} />}</button></div></header>
      {error && <div className="banner error" role="alert"><CircleAlert size={17} /><span>{error}</span><button aria-label="关闭错误" onClick={() => setError('')}><X size={15} /></button></div>}{notice && <div className="banner notice" role="status"><CircleAlert size={17} /><span>{notice}</span><button aria-label="关闭提示" onClick={() => setNotice('')}><X size={15} /></button></div>}
      <div className={`workspace-columns ${contextOpen ? '' : 'context-hidden'}`}><main className={`content ${section === 'chat' ? 'chat-content' : ''}`}>
        {section === 'chat' ? <><div className="chat-scroll">{loading ? <div className="loading-state"><LoaderCircle className="spin" size={22} />正在连接你的工作空间…</div> : messages.length === 0 ? <motion.section className="welcome" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><span className="welcome-pill"><Sparkles size={13} />为更清晰的思考而生</span><div className="welcome-symbol"><BrainCircuit size={42} strokeWidth={1.3} /></div><h1>你的知识、记忆与行动，<br /><em>始终在线。</em></h1><p className="welcome-description">连接散落的信息，记住重要的事。<br />从一个问题开始，让想法走向下一步。</p><div className="example-grid">{examples.map((example, index) => <button key={example.tag} className="example-card" onClick={() => { if (index < 2) navigate(index === 0 ? 'knowledge' : 'meetings'); else { setInput(example.prompt); inputRef.current?.focus(); } }}><div><span className={`example-icon example-icon-${index}`}><example.icon size={19} /></span><span>{example.tag}</span><ArrowRight size={15} /></div><h3>{example.title}</h3><p>{example.text}</p></button>)}</div><div className="welcome-footnote"><Layers3 size={14} />让知识彼此连接，让每次对话都有积累</div></motion.section> : <div className="message-list">{messages.map(message => <article key={message.id} className={`message message-${message.role} ${message.metadata?.failed ? 'message-failed' : ''}`}><span className={`message-avatar ${message.role === 'assistant' ? 'assistant-avatar' : ''}`}>{message.role === 'assistant' ? <BrainCircuit size={19} /> : '我'}</span><div className="message-body"><div className="message-author">{message.role === 'assistant' ? 'Cortex' : '你'}{message.metadata?.failed && <Badge value="failed" />}</div>{message.content ? <Markdown text={message.content} /> : <span className="thinking"><i /><i /><i /></span>}{message.metadata?.sources?.length ? <div className="message-sources">{message.metadata.sources.map((source, i) => <span className="source-citation" key={i}><a href={safeHref(source.text_url || source.url)} target="_blank" rel="noreferrer"><BookOpen size={12} />{source.title}</a>{source.text_url && <a href={safeHref(source.url)} target="_blank" rel="noreferrer" aria-label={`${source.title}，查看 PDF`}>查看 PDF</a>}</span>)}</div> : null}{message.metadata?.artifact && <FileCard artifact={message.metadata.artifact} />}</div></article>)}<div ref={bottomRef} /></div>}</div>
          <div className="composer-wrap">{busy && <div className="working-status"><LoaderCircle size={14} className="spin" />{status}</div>}{selectedFiles.length > 0 && <div className="selected-files">{selectedFiles.map(id => <button key={id} onClick={() => setSelectedFiles(current => current.filter(key => key !== id))}><FileText size={13} />{files.find(file => file.id === id)?.filename}<X size={12} /></button>)}</div>}<div className="composer"><textarea ref={inputRef} value={input} maxLength={12000} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void send(); } }} placeholder="问一个问题，分享一份资料，或开始一个想法…" aria-label="输入消息" rows={2} /><div className="composer-tools"><div><button className="icon-button" aria-label="上传文件" disabled={uploading || busy} onClick={() => uploadRef.current?.click()}>{uploading ? <LoaderCircle className="spin" size={18} /> : <Paperclip size={18} />}</button><span className="tool-divider" /><button className={`search-toggle ${search ? 'enabled' : ''}`} aria-pressed={search} onClick={() => setSearch(!search)}><Globe2 size={15} />联网搜索</button></div><div><small>Enter 发送 · Shift + Enter 换行</small>{busy ? <button className="stop-button" onClick={() => controllerRef.current?.abort()} aria-label="停止生成"><span /></button> : <button className="send-button" disabled={!input.trim() || !health} onClick={() => void send()} aria-label="发送消息"><ArrowUp size={20} /></button>}</div></div></div><p className="composer-note">AI 的回答可能存在偏差，重要信息请结合原始来源核实。</p></div>
        </> : <div className="page-content"><div className="page-heading"><div><span className="eyebrow">YOUR SECOND BRAIN</span><h1>{active.label}</h1><p>{active.description}</p></div>{['knowledge', 'meetings'].includes(section) && <Button disabled={uploading} onClick={() => uploadRef.current?.click()}><Upload size={15} />{uploading ? '上传中…' : section === 'meetings' ? '上传会议 TXT' : '上传文件'}</Button>}</div>
          {loading ? <div className="loading-state"><LoaderCircle className="spin" size={24} />正在加载…</div> : <>
            {section === 'knowledge' && <><button className="upload-zone" disabled={uploading} onClick={() => uploadRef.current?.click()}><span><Upload size={24} /></span><h3>让你的资料，成为答案的来源</h3><p>点击上传 PDF · 最大 20 MB · 支持可提取文字的 PDF</p></button><div className="section-heading"><h2>全部文档</h2><small>选择「用于对话」限定检索范围</small></div>{files.filter(f => f.type === 'pdf').map(file => <article className="file-row" key={file.id}><span className="file-icon"><FileText size={23} /></span><div><h3>{file.filename}</h3><Badge value={file.status} />{file.error && <p className="inline-error">{file.error}</p>}</div><div className="row-actions"><a href={`/api/files/${file.id}/content`} target="_blank" rel="noreferrer">查看原文</a><a href={`/api/files/${file.id}/text`} target="_blank" rel="noreferrer">查看提取文本</a><a href={`/api/files/${file.id}/text?download=true`}>下载 TXT</a>{file.status === 'ready' && <Button variant="outline" size="sm" onClick={() => { setSelectedFiles(current => [...new Set([...current, file.id])]); navigate('chat'); }}>用于对话<ArrowRight size={13} /></Button>}<Button size="sm" variant="outline" disabled={actionBusy !== null || busy || file.status === 'processing'} onClick={() => void reparsePdf(file)}><RefreshCw size={13} />{file.status === 'processing' ? '解析中…' : '重新解析'}</Button><Button size="sm" variant="destructive" disabled={actionBusy !== null || busy || file.status === 'processing'} onClick={() => void deletePdf(file)}><Trash2 size={13} />删除</Button></div></article>)}{!files.some(f => f.type === 'pdf') && <Empty title="知识库等待你的第一份资料" detail="上传后将提取文本、按页分块，并通过 Embedding 建立检索索引。" />}</>}
            {section === 'meetings' && <><p className="meeting-management-note">可连续上传多份会议 TXT，每份独立保存；相同内容自动去重。选择会议查看对应的摘要、行动项和风险。</p><div className="meeting-controls"><div className="filter-search"><Search size={16} /><input aria-label="搜索会议" placeholder="搜索标题、文件名、参会人或日期" value={meetingQuery} onChange={e => { setMeetingQuery(e.target.value); setSelectedMeeting(''); }} /></div><select aria-label="会议状态" value={meetingStatus} onChange={e => { setMeetingStatus(e.target.value); setSelectedMeeting(''); }}><option value="all">全部状态</option><option value="ready">已完成</option><option value="processing">分析中</option><option value="failed">失败</option></select><select aria-label="选择会议" value={selectedMeeting} onChange={e => setSelectedMeeting(e.target.value)}><option value="">全部会议（{visibleMeetingFiles.length}）</option>{visibleMeetingFiles.map(file => { const meeting = meetings.find(item => item.file_id === file.id); return <option key={file.id} value={file.id}>{meeting?.analysis.topic || file.filename} · {meeting?.analysis.time || new Date(file.created_at || '').toLocaleDateString('zh-CN')} · {file.filename}</option>; })}</select></div><div className="section-heading"><h2>会议记录 <span>{meetingFiles.length}</span></h2><small>当前显示 {shownMeetingFiles.length} 份</small></div>{shownMeetingFiles.filter(f => f.status !== 'ready').map(file => <div className="file-row" key={file.id}><FileText size={20} /><div><h3>{file.filename}</h3><Badge value={file.status} />{file.error && <p className="inline-error">{file.error}</p>}</div><div className="row-actions"><a href={`/api/files/${file.id}/content`} target="_blank" rel="noreferrer">查看原文</a>{file.status === 'failed' && <Button size="sm" variant="outline" disabled={actionBusy !== null || busy} onClick={() => void runAction(file.id, () => api(`/files/${file.id}/retry`, { method: 'POST' }))}>重新分析</Button>}<Button size="sm" variant="destructive" disabled={actionBusy !== null || busy || file.status === 'processing'} onClick={() => void deleteMeeting(file)}><Trash2 size={13} />删除</Button></div></div>)}{shownMeetings.map(meeting => <article className="meeting-card" key={meeting.id}><div className="card-top"><Users size={19} /><small>{new Date(meeting.analyzed_at).toLocaleString('zh-CN')}</small><a href={`/api/files/${meeting.file_id}/content`} target="_blank" rel="noreferrer">查看原文<ArrowRight size={13} /></a><Button variant="destructive" size="sm" disabled={actionBusy !== null || busy || files.find(file => file.id === meeting.file_id)?.status === 'processing' || meeting.tasks.some(task => task.email_status === 'sending')} onClick={() => { const file = files.find(item => item.id === meeting.file_id); if (file) void deleteMeeting(file); }}><Trash2 size={13} />删除会议</Button></div><h2>{meeting.analysis.topic}</h2><span className="muted">{meeting.filename}</span><p>{meeting.analysis.summary}</p><div className="task-meta"><span><Users size={14} />{meeting.analysis.people.join('、') || '参会人未明确'}</span><span><Clock3 size={14} />{meeting.analysis.time || '时间未明确'}</span></div>{meeting.analysis.decisions.length > 0 && <><h4>会议决定</h4><ul>{meeting.analysis.decisions.map((item, i) => <li key={i}>{item}</li>)}</ul></>}{meeting.analysis.action_items.length > 0 && <><h4>行动项</h4><ul>{meeting.analysis.action_items.map((item, i) => <li key={i}>{item}</li>)}</ul></>}<div className="section-heading"><h4>风险与行动</h4><span>{meeting.tasks.length} 项</span></div>{meeting.tasks.length ? <div className="task-grid">{meeting.tasks.map(taskCard)}</div> : <div className="safe-note"><CircleCheck size={17} />未识别到有效风险，未创建风险待办或发送邮件。</div>}</article>)}{meetingFiles.length > 0 && shownMeetingFiles.length === 0 && <Empty title="没有匹配的会议" detail="请调整搜索词或状态筛选。" />}{!meetingFiles.length && <Empty title="把讨论，变成下一步行动" detail="上传 UTF-8 或 GB18030 编码的会议 TXT，自动分析摘要、风险和待办。" />}</>}
            {section === 'memories' && <><div className="section-heading"><h2>全部记忆</h2><Button size="sm" disabled={actionBusy !== null || busy} onClick={() => { setMemoryError(''); setMemoryOpen(true); }}><Plus size={14} />新建记忆</Button></div><div className="filters"><div className="filter-search"><Search size={16} /><input aria-label="搜索记忆" placeholder="搜索记忆摘要" value={filter} onChange={e => setFilter(e.target.value)} /></div><Button variant="outline" size="sm" disabled={actionBusy !== null || busy} onClick={() => void runAction('reindex', async () => { const result = await api<{ indexed: number }>('/memories/reindex', { method: 'POST' }); setNotice(`已为 ${result.indexed} 条记忆建立语义索引`); })}><RefreshCw size={14} />重建待处理索引</Button></div><div className="memory-filters">{(['person', 'time', 'location', 'topic'] as const).map((key, i) => <input key={key} aria-label={['人物', '时间', '地点', '主题'][i]} placeholder={['人物', '时间', '地点', '主题'][i]} value={memoryFilters[key]} onChange={e => setMemoryFilters(current => ({ ...current, [key]: e.target.value }))} />)}</div><div className="memory-grid">{memories.filter(m => m.summary.includes(filter) && (!memoryFilters.person || m.person?.includes(memoryFilters.person)) && (!memoryFilters.time || m.time_text?.includes(memoryFilters.time)) && (!memoryFilters.location || m.location?.includes(memoryFilters.location)) && (!memoryFilters.topic || m.topic?.includes(memoryFilters.topic))).map(memory => <article className="memory-card" key={memory.id}><div className="card-top"><span><BrainCircuit size={16} />{memory.topic || '长期事实'}</span><small>{memory.source_type === 'manual' ? '手动录入' : `${Math.round(memory.confidence * 100)}% 置信度`}</small></div><h3>{memory.summary}</h3><div className="memory-tags">{[memory.person, memory.time_text, memory.location].filter(Boolean).map((value, i) => <span key={i}>{value}</span>)}</div><blockquote>{memory.evidence}</blockquote><div className="memory-bottom"><small>{memory.source_type === 'manual' ? '手动新建' : memory.source_type === 'chat' ? '来自对话' : '来自会议'} · {memory.index_status === 'ready' ? '已建立语义索引' : '索引待处理'}</small><div className="memory-actions"><a href={`/api/memories/${memory.id}/source`} target="_blank" rel="noreferrer">追溯原文<ArrowRight size={13} /></a><Button variant="destructive" size="sm" disabled={actionBusy !== null || busy} onClick={() => void deleteMemory(memory)}><Trash2 size={12} />删除</Button></div></div></article>)}</div>{!memories.length && <Empty title="重要的事，会在这里留下" detail="点击新建记忆手动录入，也可通过对话或会议自动提取，新会话也可检索。" />}</>}
            {section === 'tasks' && <><div className="section-heading"><h2>风险待办</h2><Button variant="outline" size="sm" disabled={actionBusy !== null || busy} onClick={() => void openMailSettings()}><Mail size={14} />邮件设置</Button></div><div className="filters"><div className="filter-search"><Search size={16} /><input aria-label="搜索待办" placeholder="搜索待办事项" value={filter} onChange={e => setFilter(e.target.value)} /></div><span className="muted">{openTasks.length} 项待跟进</span></div><div className="task-grid">{tasks.filter(t => (t.title + t.description).includes(filter)).map(taskCard)}</div>{!tasks.length && <Empty title="每一件重要的事，都有着落" detail="会议中识别的有效风险会自动生成待办，邮件状态会如实记录。" />}</>}
            {section === 'slides' && <><form className="slides-form" onSubmit={e => { e.preventDefault(); void runAction('slides', async () => { await api('/slides', { method: 'POST', body: JSON.stringify({ topic: slideTopic, pages, use_knowledge: useKnowledge }) }); setNotice('生成任务已创建，完成后将显示下载入口。'); }); }}><div className="form-intro"><span className="file-icon purple"><Presentation size={23} /></span><div><h2>让一个想法，成为一份好演示</h2><p>专业 16:9 版式 · 真实 PowerPoint 文件</p></div></div><label htmlFor="slide-topic">你想介绍什么？</label><textarea id="slide-topic" required maxLength={2000} rows={3} value={slideTopic} onChange={e => setSlideTopic(e.target.value)} placeholder="例如：AI Agent 在企业中的应用，面向业务管理者，重点介绍场景、价值与落地路径。" /><div className="form-bottom"><label>页数<select aria-label="页数" value={pages} onChange={e => setPages(Number(e.target.value))}>{[5, 6, 8, 10, 12, 16, 20].map(n => <option key={n} value={n}>{n} 页</option>)}</select></label><label className="checkbox-label"><input type="checkbox" checked={useKnowledge} onChange={e => setUseKnowledge(e.target.checked)} />使用相关知识与会议内容</label><Button type="submit" disabled={actionBusy === 'slides' || !slideTopic.trim()}><Sparkles size={15} />生成演示文稿</Button></div></form><div className="section-heading"><h2>我的演示文稿 <span>{artifacts.length}</span></h2></div><div className="artifact-list">{artifacts.map(a => <FileCard key={a.id} artifact={a} disabled={actionBusy !== null || busy} onDelete={() => void deleteArtifact(a)} />)}</div>{!artifacts.length && <Empty title="下一次精彩表达，从这里开始" detail="生成任务完成后，这里会出现真实的 .pptx 下载文件。" />}</>}
            {['slides', 'meetings', 'knowledge'].includes(section) && <div className="job-section"><div className="section-heading"><h2>最近任务</h2><span>执行记录</span></div>{jobs.filter(j => section === 'slides' ? j.type === 'slides' : section === 'knowledge' ? j.type === 'pdf' : ['meeting', 'txt'].includes(j.type)).slice(0, 8).map(job => <div className="job-row" key={job.id}>{['queued', 'running'].includes(job.status) ? <LoaderCircle className="spin" size={16} /> : job.status === 'succeeded' ? <CircleCheck size={16} /> : <CircleAlert size={16} />}<div><strong>{job.type === 'slides' ? '演示文稿生成' : job.type === 'pdf' ? 'PDF 知识索引' : '会议分析'}</strong>{job.error && <p className="inline-error">{job.error}</p>}</div><Badge value={job.status} /></div>)}</div>}
          </>}
        </div>}
      </main>{contextOpen && <aside className="context-panel"><div className="context-heading"><Layers3 size={17} /><h2>上下文</h2><span>CONTEXT</span></div><p className="context-description">把相关的信息，放在手边。</p><section className="context-section"><div className="context-title"><BookOpen size={15} /><h3>相关来源</h3><span>{sources.length}</span></div>{sources.length ? sources.map((source, i) => <a className="context-source" key={i} href={safeHref(source.text_url || source.url)} target="_blank" rel="noreferrer"><FileText size={16} /><div><strong>{source.title}</strong><p>{source.content.slice(0, 70)}</p></div><ChevronRight size={13} /></a>) : <div className="context-empty"><FileText size={23} strokeWidth={1.3} /><p>对话引用的文档与搜索来源<br />会出现在这里</p></div>}</section><section className="context-section"><div className="context-title"><BrainCircuit size={15} /><h3>最近记忆</h3><button onClick={() => navigate('memories')}>查看全部<ChevronRight size={12} /></button></div>{memories.slice(0, 3).map(m => <a className="context-memory" key={m.id} href={`/api/memories/${m.id}/source`} target="_blank" rel="noreferrer"><small>{m.topic || m.person || '长期事实'}</small><p>{m.summary}</p></a>)}{!memories.length && <p className="context-hint">还没有记忆。开始对话或上传会议，逐步建立属于你的知识脉络。</p>}</section><section className="context-section"><div className="context-title"><ListTodo size={15} /><h3>待跟进</h3><span>{openTasks.length}</span></div>{openTasks.slice(0, 3).map(t => <button className="context-task" key={t.id} onClick={() => navigate('tasks')}><span className="task-square" /><div><strong>{t.title}</strong><small>{t.owner || '责任人未明确'} · {t.deadline || '期限待明确'}</small></div></button>)}{!openTasks.length && <div className="all-clear"><CheckCheck size={18} /><span>暂时没有待跟进的事项</span></div>}</section><div className="context-bottom"><ShieldCheck size={18} /><p>有来源的答案，<br />有积累的思考。</p></div></aside>}</div>
    </div>
    {settingsOpen && <div className="modal-scrim" onClick={() => setSettingsOpen(false)}><section className="settings-modal" role="dialog" aria-modal="true" aria-label="服务配置" onClick={e => e.stopPropagation()}><div className="modal-heading"><h2>你的外脑，准备好了吗？</h2><button className="icon-button" aria-label="关闭配置" onClick={() => setSettingsOpen(false)}><X size={19} /></button></div><p>模型配置从根目录 <code>.env</code> 读取，修改后重启后端。邮件可在「待办事项 → 邮件设置」中配置并立即生效。密钥仅保留在后端。</p>{[{ id: 'chat', name: '对话模型', keys: 'CHAT_BASE_URL / CHAT_API_KEY / CHAT_MODEL' }, { id: 'embedding', name: 'Embedding · 知识与记忆检索', keys: 'EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL' }, { id: 'search', name: health?.search_provider === 'deepseek' ? 'DeepSeek 联网搜索' : 'Tavily 联网搜索', keys: health?.search_provider === 'deepseek' ? '复用后端 CHAT_API_KEY' : 'TAVILY_API_KEY' }, { id: 'smtp', name: 'SMTP 风险提醒', keys: 'SMTP_HOST / SMTP_FROM / SMTP_ALLOWED_RECIPIENTS 等' }].map(item => <div className="config-row" key={item.id}><div><strong>{item.name}</strong><small>{item.keys}</small></div><span className={`config-status ${health?.capabilities[item.id] ? 'configured' : ''}`}>{health?.capabilities[item.id] ? '已填写' : '待配置'}</span></div>)}<div className="safe-note"><CircleAlert size={16} />「已填写」仅表示配置存在，不代表外部服务已验证。</div><Button variant="outline" onClick={() => void refresh()}><RefreshCw size={15} />刷新状态</Button></section></div>}
    {mailOpen && mailSettings && <div className="modal-scrim" onClick={() => { if (actionBusy !== 'save-smtp') { setMailOpen(false); setMailPassword(''); } }}><form className="settings-modal memory-modal" role="dialog" aria-modal="true" aria-labelledby="mail-dialog-title" onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === 'Escape' && actionBusy !== 'save-smtp') { setMailOpen(false); setMailPassword(''); } }} onSubmit={e => { e.preventDefault(); void saveMailSettings(); }}><div className="modal-heading"><h2 id="mail-dialog-title">邮件设置</h2><button type="button" className="icon-button" aria-label="关闭邮件设置" disabled={actionBusy === 'save-smtp'} onClick={() => { setMailOpen(false); setMailPassword(''); }}><X size={18} /></button></div><p>QQ 邮箱需先开启 SMTP 服务，并使用授权码。保存设置不会发送邮件；新会议的风险提醒会发送给以下全部收件人。</p><fieldset disabled={actionBusy === 'save-smtp'}><div className="memory-inputs"><label>发件邮箱<input type="email" required autoFocus value={mailSettings.smtp_user} onChange={e => { const account = e.target.value; setMailSettings(current => current && ({ ...current, smtp_user: account, smtp_from: account })); }} autoComplete="username" /></label><label>发件人地址<input type="email" required value={mailSettings.smtp_from} onChange={e => setMailSettings(current => current && ({ ...current, smtp_from: e.target.value }))} /></label></div><label>SMTP 授权码<span>{mailSettings.password_set ? '已保存 · 留空保留原凭据' : '尚未保存'}</span><input type="password" value={mailPassword} onChange={e => setMailPassword(e.target.value)} autoComplete="new-password" placeholder="QQ 邮箱填写 16 位授权码，非登录密码" /></label><div className="memory-inputs"><label>SMTP 服务器<input required maxLength={253} value={mailSettings.smtp_host} onChange={e => setMailSettings(current => current && ({ ...current, smtp_host: e.target.value }))} /></label><label>端口<input type="number" required min={1} max={65535} value={mailSettings.smtp_port} onChange={e => setMailSettings(current => current && ({ ...current, smtp_port: Number(e.target.value) }))} /></label></div><label>加密方式<select value={mailSettings.smtp_use_ssl ? 'ssl' : mailSettings.smtp_starttls ? 'starttls' : 'none'} onChange={e => { const mode = e.target.value; setMailSettings(current => current && ({ ...current, smtp_use_ssl: mode === 'ssl', smtp_starttls: mode === 'starttls' })); }}><option value="ssl">SSL/TLS（通常端口 465）</option><option value="starttls">STARTTLS（通常端口 587）</option><option value="none">无加密（仅用于受控本地邮件服务）</option></select></label><label>收件邮箱<span>多个邮箱用换行或逗号分隔；留空时不发送</span><textarea rows={3} value={mailRecipients} onChange={e => setMailRecipients(e.target.value)} placeholder="receiver@example.com" /></label></fieldset>{mailError && <p className="inline-error" role="alert">{mailError}</p>}<div className="memory-form-actions"><Button type="button" variant="outline" disabled={actionBusy === 'save-smtp'} onClick={() => { setMailOpen(false); setMailPassword(''); }}>取消</Button><Button type="submit" disabled={actionBusy !== null}>{actionBusy === 'save-smtp' ? '正在保存…' : '保存设置'}</Button></div></form></div>}
    {memoryOpen && <div className="modal-scrim" onClick={() => { if (actionBusy !== 'create-memory') setMemoryOpen(false); }}><form className="settings-modal memory-modal" role="dialog" aria-modal="true" aria-labelledby="memory-dialog-title" onClick={e => e.stopPropagation()} onKeyDown={e => { if (e.key === 'Escape' && actionBusy !== 'create-memory') setMemoryOpen(false); }} onSubmit={e => { e.preventDefault(); void createMemory(); }}><div className="modal-heading"><h2 id="memory-dialog-title">新建长期记忆</h2><button type="button" className="icon-button" aria-label="关闭新建记忆" disabled={actionBusy === 'create-memory'} onClick={() => setMemoryOpen(false)}><X size={18} /></button></div><p>直接保存你填写的事实；人物、时间、地点、主题和原文说明可选。</p><fieldset disabled={actionBusy === 'create-memory'}><label>记忆内容<span>必填 · 最多 1000 字</span><textarea required maxLength={1000} rows={3} autoFocus value={memoryDraft.summary} onChange={e => setMemoryDraft(current => ({ ...current, summary: e.target.value }))} placeholder="例如：我叫麦兜，偏好使用中文回答。" /></label><div className="memory-inputs">{(['person', 'time_text', 'location', 'topic'] as const).map((key, i) => <label key={key}>{['人物', '时间', '地点', '主题'][i]}<input maxLength={150} value={memoryDraft[key]} onChange={e => setMemoryDraft(current => ({ ...current, [key]: e.target.value }))} /></label>)}</div><label>原文说明<span>可选 · 留空时使用记忆内容</span><textarea maxLength={2000} rows={3} value={memoryDraft.evidence} onChange={e => setMemoryDraft(current => ({ ...current, evidence: e.target.value }))} /></label></fieldset>{memoryError && <p className="inline-error" role="alert">{memoryError}</p>}<div className="memory-form-actions"><Button type="button" variant="outline" disabled={actionBusy === 'create-memory'} onClick={() => setMemoryOpen(false)}>取消</Button><Button type="submit" disabled={actionBusy !== null || !memoryDraft.summary.trim()}>{actionBusy === 'create-memory' ? <><LoaderCircle className="spin" size={14} />正在保存…</> : '保存记忆'}</Button></div></form></div>}
    {rename && <div className="modal-scrim" onClick={() => setRename(null)}><form className="settings-modal rename-modal" onClick={e => e.stopPropagation()} onSubmit={e => { e.preventDefault(); void runAction('rename', async () => { await api(`/conversations/${rename}`, { method: 'PATCH', body: JSON.stringify({ title: renameTitle }) }); setRename(null); }); }}><div className="modal-heading"><h2>重命名会话</h2><button type="button" className="icon-button" aria-label="取消" onClick={() => setRename(null)}><X size={18} /></button></div><input aria-label="会话名称" required maxLength={80} value={renameTitle} onChange={e => setRenameTitle(e.target.value)} autoFocus /><Button type="submit" disabled={actionBusy === 'rename'}>保存名称</Button></form></div>}
  </div>;
}
