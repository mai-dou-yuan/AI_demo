'use client';
import { useCallback, useEffect, useState } from 'react';
import { BrainCircuit, ArrowRight, KeyRound, LoaderCircle, LockKeyhole, ShieldCheck, UserRound } from 'lucide-react';
import { api, setCsrfToken } from '@/lib/api';
import Workspace from './workspace';
import Link from 'next/link';

type Session = { authenticated: boolean; username: string; must_change_password: boolean; csrf_token: string };
const message = (error: unknown) => error instanceof Error ? error.message : '暂时无法连接服务，请稍后重试';

export default function AuthGate() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [changing, setChanging] = useState(false);
  const accept = useCallback((data: Session) => { setCsrfToken(data.csrf_token); setSession(data); setError(''); }, []);
  useEffect(() => {
    const expired = () => { setSession(null); setChanging(false); setCsrfToken(''); setCurrentPassword(''); setNewPassword(''); setConfirmation(''); };
    window.addEventListener('cortex:unauthorized', expired);
    const check = async () => {
      try { accept(await api<Session>('/auth/session')); }
      catch (e) { if (!(e instanceof Error) || e.message !== '请先登录') setError(message(e)); }
      finally { setLoading(false); }
    };
    void check();
    const timer = setInterval(() => { if (document.visibilityState === 'visible') void check(); }, 60000);
    return () => { window.removeEventListener('cortex:unauthorized', expired); clearInterval(timer); };
  }, [accept]);
  async function login() {
    setWorking(true); setError('');
    try { accept(await api<Session>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })); setPassword(''); }
    catch (e) { setError(message(e)); }
    finally { setWorking(false); }
  }
  async function logout() {
    setWorking(true); setError('');
    try { await api('/auth/logout', { method: 'POST' }); setCsrfToken(''); setSession(null); setChanging(false); }
    catch (e) { setError(message(e)); }
    finally { setWorking(false); }
  }
  async function changePassword() {
    if (newPassword !== confirmation) { setError('两次输入的新密码不一致'); return; }
    setWorking(true); setError('');
    try {
      accept(await api<Session>('/auth/password', { method: 'POST', body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }));
      setCurrentPassword(''); setNewPassword(''); setConfirmation(''); setChanging(false);
    } catch (e) { setError(message(e)); }
    finally { setWorking(false); }
  }
  if (loading) return <div className="auth-loading"><LoaderCircle className="spin" size={24} /><span>正在验证会话…</span></div>;
  if (session && !session.must_change_password && !changing) return <div className="authenticated-shell"><Workspace username={session.username} accountBusy={working} accountError={error} onChangePassword={() => { setChanging(true); setError(''); }} onLogout={() => void logout()} /></div>;
  const change = Boolean(session);
  return <main className="auth-page"><section className="auth-story"><Link className="auth-brand" href="/" aria-label="Cortex 首页"><span><BrainCircuit size={28} /></span>Cortex<small>SECOND BRAIN</small></Link><div className="auth-story-copy"><span className="auth-eyebrow">YOUR PRIVATE WORKSPACE</span><h1>让知识有积累，<br />让思考有归处。</h1><p>你的资料、记忆与行动，<br />在一个属于自己的工作空间里相遇。</p><div className="auth-story-symbol" aria-hidden="true"><BrainCircuit size={100} strokeWidth={.8} /></div></div><p className="auth-story-footer"><LockKeyhole size={15} />先验证身份，再进入工作空间</p></section><section className="auth-entry"><div className="auth-card"><div className="auth-lock"><LockKeyhole size={24} /></div><span className="auth-eyebrow">CORTEX WORKSPACE</span><h2>{change ? '设置你的登录密码' : '欢迎回来'}</h2><p>{change ? session?.must_change_password ? '首次登录，请更换初始密码后继续。' : '修改密码后，其他已登录会话将失效。' : '登录后访问你的知识、记忆与待办。'}</p><form onSubmit={e => { e.preventDefault(); if (!working) void (change ? changePassword() : login()); }}><fieldset disabled={working}>{!change ? <><label htmlFor="login-account">账号</label><div className="auth-input"><UserRound size={17} /><input id="login-account" autoFocus autoComplete="username" required maxLength={64} value={username} onChange={e => setUsername(e.target.value)} /></div><label htmlFor="login-password">密码</label><div className="auth-input"><KeyRound size={17} /><input id="login-password" type="password" autoComplete="current-password" required maxLength={256} value={password} onChange={e => setPassword(e.target.value)} /></div></> : <><label htmlFor="old-password">当前密码</label><div className="auth-input"><input id="old-password" autoFocus type="password" autoComplete="current-password" required maxLength={256} value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></div><label htmlFor="new-password">新密码<span>至少 12 个字符</span></label><div className="auth-input"><input id="new-password" type="password" autoComplete="new-password" required minLength={12} maxLength={256} value={newPassword} onChange={e => setNewPassword(e.target.value)} /></div><label htmlFor="confirm-password">再次输入新密码</label><div className="auth-input"><input id="confirm-password" type="password" autoComplete="new-password" required minLength={12} maxLength={256} value={confirmation} onChange={e => setConfirmation(e.target.value)} /></div></>}</fieldset>{error && <div className="auth-error" role="alert">{error}</div>}<button className="auth-submit" type="submit" disabled={working}>{working ? <><LoaderCircle className="spin" size={17} />正在处理…</> : <>{change ? '保存并进入工作空间' : '登录工作空间'}<ArrowRight size={17} /></>}</button>{change && !session?.must_change_password && <button type="button" className="auth-back" onClick={() => { setChanging(false); setError(''); }} disabled={working}>返回工作空间</button>}{change && session?.must_change_password && <button type="button" className="auth-back" onClick={() => void logout()} disabled={working}>退出登录</button>}</form>{!change && <div className="auth-help"><ShieldCheck size={16} /><p>仅允许已配置的本地账号登录。<br />首次使用或忘记密码，请在服务器终端管理账号。</p></div>}</div><small className="auth-footer">Cortex · 你的 AI 外脑</small></section></main>;
}
