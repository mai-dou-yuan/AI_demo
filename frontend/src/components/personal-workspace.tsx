'use client';

import { useEffect, useId, useRef, useState } from 'react';
import { ChevronUp, KeyRound, LogOut, Mail, Settings2, ShieldCheck, UserRound } from 'lucide-react';

type Props = {
  username: string;
  busy: boolean;
  error?: string;
  onChangePassword: () => void;
  onLogout: () => void;
  onSettings: () => void;
  onMailSettings: () => void;
};

export default function PersonalWorkspace({ username, busy, error, onChangePassword, onLogout, onSettings, onMailSettings }: Props) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setOpen(false); trigger.current?.focus(); }
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape); };
  }, [open]);

  function choose(action: () => void) {
    setOpen(false);
    action();
  }

  return <div className="personal-workspace" ref={root} onBlur={event => {
    if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false);
  }}>
    <button className={`profile personal-trigger${open ? ' is-open' : ''}`} ref={trigger} aria-expanded={open} aria-controls={id} onClick={() => setOpen(value => !value)}>
      <span className="personal-trigger-icon"><UserRound size={18} /></span>
      <span>个人工作空间<small>账号与偏好设置</small></span>
      <ChevronUp size={16} />
    </button>
    {open && <section className="personal-panel" id={id} aria-label="个人工作空间设置">
      <div className="personal-identity"><span className="personal-avatar">{username.slice(0, 1).toUpperCase()}</span><div><strong title={username}>{username}</strong><small><ShieldCheck size={11} />工作空间所有者</small></div></div>
      <div className="personal-group"><p>工作空间</p><button disabled={busy} onClick={() => choose(onSettings)}><Settings2 size={16} /><span>服务配置<small>模型与连接状态</small></span></button><button disabled={busy} onClick={() => choose(onMailSettings)}><Mail size={16} /><span>邮件设置<small>发件邮箱与收件人</small></span></button></div>
      <div className="personal-group"><p>账号与安全</p><button disabled={busy} onClick={() => choose(onChangePassword)}><KeyRound size={16} /><span>修改密码<small>更新登录凭据</small></span></button></div>
      <div className="personal-signout"><button disabled={busy} onClick={() => choose(onLogout)}><LogOut size={16} /><span>{busy ? '请稍候…' : '退出登录'}</span></button></div>
    </section>}
    {error && <p className="personal-error" role="alert">{error}</p>}
  </div>;
}
