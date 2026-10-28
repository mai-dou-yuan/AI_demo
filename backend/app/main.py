import asyncio
import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from .checkpoints import LocalSqliteSaver

from .core import AppError, Database, Settings, dump, now, uid
from .graph import build_graph
from .providers import Providers
from .schemas import ChatInput, ConversationInput, MemoryInput, SlidesInput, SmtpInput, LoginInput, PasswordInput
from .auth import Auth, COOKIE, SecurityMiddleware, digest
from .mail_settings import load_smtp, public_smtp, save_smtp
from .services import Services, decode_txt, pdf_chunks, pdf_pages, pdf_paragraphs

log = logging.getLogger('cortex')
os.environ.setdefault('LANGGRAPH_STRICT_MSGPACK', 'true')


def create_app(settings=None, providers=None):
    settings = settings or Settings()
    db = Database(settings.storage_dir)
    load_smtp(settings, db.root)
    provider = providers or Providers(settings)
    services = Services(settings, db, provider)
    auth = Auth(settings, db.root)
    running = set()
    conversation_locks = {}

    @asynccontextmanager
    async def lifespan(app):
        with LocalSqliteSaver.from_conn_string(str(db.root / 'checkpoints.sqlite3')) as saver:
            app.state.graph = build_graph(services, saver)
            yield
            for task in list(running):
                task.cancel()
            if running:
                await asyncio.gather(*list(running), return_exceptions=True)

    app = FastAPI(title='Cortex · Second Brain', version='0.1.0', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db, app.state.services = db, services
    app.state.auth = auth
    app.add_middleware(SecurityMiddleware, auth=auth)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default errors include submitted inputs, potentially credentials.
        return JSONResponse({'detail': '请求参数无效，请检查字段格式和长度'}, status_code=422)

    @app.post('/api/auth/login')
    async def login(data: LoginInput, request: Request):
        verified_hash = auth.login(data.username, data.password.get_secret_value(), request.client.host if request.client else 'unknown')
        response = JSONResponse({})
        token = auth.issue(response, verified_hash)
        response.body = json.dumps(auth.status(token)).encode()
        response.headers['content-length'] = str(len(response.body))
        return response

    @app.get('/api/auth/session')
    async def auth_session(request: Request):
        return auth.status(request.cookies[COOKIE])

    @app.post('/api/auth/logout')
    async def logout(request: Request):
        with auth.connect() as connection:
            connection.execute('DELETE FROM sessions WHERE token_hash=?', (digest(request.cookies[COOKIE]),))
        auth.audit('logout')
        response = JSONResponse({'logged_out': True})
        response.delete_cookie(COOKIE, path='/', secure=bool(auth.public_origin), httponly=True, samesite='strict')
        return response

    @app.post('/api/auth/password')
    async def change_password(data: PasswordInput, request: Request):
        verified_hash = auth.change_password(data.current_password.get_secret_value(), data.new_password.get_secret_value(), request.client.host if request.client else 'unknown')
        response = JSONResponse({})
        token = auth.issue(response, verified_hash)
        response.body = json.dumps(auth.status(token)).encode()
        response.headers['content-length'] = str(len(response.body))
        return response

    @app.get('/api/settings/smtp')
    async def get_smtp():
        return public_smtp(settings)

    @app.put('/api/settings/smtp')
    async def update_smtp(data: SmtpInput):
        if any(lock.locked() for lock in services.mail_locks.values()):
            raise AppError('邮件正在发送，请稍后保存设置', 409)
        return save_smtp(settings, db.root, data)

    @app.exception_handler(AppError)
    async def app_error(request, exc):
        return JSONResponse({'detail': exc.message}, status_code=exc.status)

    @app.exception_handler(Exception)
    async def unexpected(request, exc):
        log.error('Unhandled request failure: %s', type(exc).__name__)
        return JSONResponse({'detail': '服务内部错误，请检查后端日志'}, status_code=500)

    def start_job(job_id, operation, file_id=None):
        async def run():
            db.execute("UPDATE jobs SET status='running',progress=15 WHERE id=?", (job_id,))
            try:
                result = await operation()
                warning = None
                if isinstance(result, tuple):
                    result, warning = result
                db.execute("UPDATE jobs SET status='succeeded',progress=100,result_id=?,error=? WHERE id=?", (result, warning, job_id))
                if file_id:
                    db.execute("UPDATE files SET status='ready',error=? WHERE id=?", (warning, file_id))
            except asyncio.CancelledError:
                db.execute("UPDATE jobs SET status='failed',error='服务停止，任务已中断' WHERE id=?", (job_id,))
                if file_id:
                    db.execute("UPDATE files SET status='failed',error='任务中断' WHERE id=?", (file_id,))
                raise
            except Exception as exc:
                error = exc.message if isinstance(exc, AppError) else f'任务失败（{type(exc).__name__}）'
                log.warning('Job %s failed: %s', job_id, type(exc).__name__)
                db.execute("UPDATE jobs SET status='failed',error=? WHERE id=?", (error, job_id))
                if file_id:
                    db.execute("UPDATE files SET status='failed',error=? WHERE id=?", (error, file_id))
        task = asyncio.create_task(run())
        running.add(task)
        task.add_done_callback(running.discard)

    @app.get('/api/health')
    async def health():
        return {'status': 'ok', 'capabilities': settings.capabilities(), 'search_provider': settings.effective_search_provider(), 'models': {'chat': settings.chat_model, 'embedding': settings.embedding_model}}

    @app.get('/api/conversations')
    async def conversations():
        return db.all('SELECT * FROM conversations ORDER BY updated_at DESC')

    @app.post('/api/conversations', status_code=201)
    async def create_conversation(data: ConversationInput):
        row = dict(id=uid(), title=data.title, created_at=now(), updated_at=now())
        db.insert('conversations', row)
        return row

    @app.patch('/api/conversations/{key}')
    async def rename_conversation(key: str, data: ConversationInput):
        db.one('SELECT id FROM conversations WHERE id=?', (key,), required=True)
        db.execute('UPDATE conversations SET title=?,updated_at=? WHERE id=?', (data.title, now(), key))
        return {'id': key, 'title': data.title}

    @app.get('/api/conversations/{key}/messages')
    async def messages(key: str):
        db.one('SELECT id FROM conversations WHERE id=?', (key,), required=True)
        rows = db.all('SELECT * FROM messages WHERE conversation_id=? ORDER BY rowid', (key,))
        for row in rows:
            row['metadata'] = json.loads(row.pop('metadata_json'))
        return rows

    @app.post('/api/chat/stream')
    async def chat(data: ChatInput):
        db.one('SELECT id FROM conversations WHERE id=?', (data.conversation_id,), required=True)
        if not data.message.strip():
            raise AppError('消息不能为空')
        for file_id in data.file_ids:
            db.one("SELECT id FROM files WHERE id=? AND type='pdf' AND status='ready'", (file_id,), required=True)
        lock = conversation_locks.setdefault(data.conversation_id, asyncio.Lock())
        if lock.locked():
            raise AppError('当前会话正在生成回答，请稍后再试', 409)
        await lock.acquire()
        try:
            message_id = db.message(data.conversation_id, 'user', data.message)
        except BaseException:
            lock.release()
            raise
        async def events():
            try:
                async for event in app.state.graph.astream({**data.model_dump(), 'message_id': message_id}, {'configurable': {'thread_id': data.conversation_id}}, stream_mode='custom'):
                    yield 'data: ' + dump(event) + '\n\n'
                yield 'data: ' + dump({'type': 'done'}) + '\n\n'
            except asyncio.CancelledError:
                db.message(data.conversation_id, 'assistant', '生成已中断', {'failed': True})
                raise
            except Exception as exc:
                error = exc.message if isinstance(exc, AppError) else f'对话失败（{type(exc).__name__}）'
                db.message(data.conversation_id, 'assistant', error, {'failed': True})
                yield 'data: ' + dump({'type': 'error', 'content': error}) + '\n\n'
            finally:
                lock.release()
        return StreamingResponse(events(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @app.get('/api/files')
    async def files():
        return db.all('SELECT id,filename,type,status,error,created_at FROM files ORDER BY created_at DESC')

    @app.post('/api/files/upload', status_code=202)
    async def upload(file: UploadFile = File(...)):
        filename = (file.filename or 'upload').replace('\\', '/').split('/')[-1]
        suffix = Path(filename).suffix.lower()
        if suffix not in ('.pdf', '.txt'):
            raise AppError('仅支持 PDF 和 TXT 文件')
        limit = settings.max_upload_mb * 1024 * 1024
        data = bytearray()
        while block := await file.read(1024 * 1024):
            data.extend(block)
            if len(data) > limit:
                raise AppError(f'文件超过 {settings.max_upload_mb} MB 限制', 413)
        content = bytes(data)
        if suffix == '.pdf':
            pdf_chunks(content)
        else:
            text = decode_txt(content)
            if len(text) > 60000:
                raise AppError('会议原文超过 60000 字，请拆分后上传')
        digest = hashlib.sha256(content).hexdigest()
        existing = db.one('SELECT id,status FROM files WHERE sha256=?', (digest,))
        if existing:
            job = db.one('SELECT id FROM jobs WHERE result_id=? ORDER BY created_at DESC LIMIT 1', (existing['id'],))
            # Meetings use meeting_id as successful result; locate via file relationship too.
            if not job:
                job = db.one('SELECT id FROM jobs WHERE result_id IN (SELECT id FROM meetings WHERE file_id=?) ORDER BY created_at DESC LIMIT 1', (existing['id'],))
            return {'file_id': existing['id'], 'job_id': job['id'] if job else None, 'duplicate': True, 'status': existing['status']}
        key = uid()
        relative = f'uploads/{key}{suffix}'
        (db.root / relative).write_bytes(content)
        db.insert('files', dict(id=key, filename=filename[:200], type=suffix[1:], sha256=digest, path=relative, status='processing', created_at=now()))
        job_id = db.job('pdf' if suffix == '.pdf' else 'meeting', key)
        start_job(job_id, lambda: services.process_pdf(key) if suffix == '.pdf' else services.process_meeting(key), key)
        return {'file_id': key, 'job_id': job_id, 'duplicate': False}

    @app.post('/api/files/{key}/retry', status_code=202)
    async def retry_file(key: str):
        file = db.one('SELECT * FROM files WHERE id=?', (key,), required=True)
        if file['status'] != 'failed':
            raise AppError('仅失败文件可以重试', 409)
        db.execute("UPDATE files SET status='processing',error=NULL WHERE id=?", (key,))
        job_id = db.job(file['type'], key)
        start_job(job_id, lambda: services.process_pdf(key) if file['type'] == 'pdf' else services.process_meeting(key), key)
        return {'job_id': job_id, 'file_id': key}

    @app.get('/api/files/{key}/content')
    async def file_content(key: str):
        file = db.one('SELECT * FROM files WHERE id=?', (key,), required=True)
        data = db.safe_path(file['path']).read_bytes()
        if file['type'] == 'txt':
            return Response(decode_txt(data), media_type='text/plain; charset=utf-8')
        return Response(data, media_type='application/pdf', headers={'Content-Disposition': 'inline'})

    @app.post('/api/files/{key}/reparse', status_code=202)
    async def reparse_pdf(key: str):
        file = db.one('SELECT * FROM files WHERE id=?', (key,), required=True)
        if file['type'] != 'pdf':
            raise AppError('此接口仅支持重新解析知识库 PDF')
        if file['status'] == 'processing' or db.one("SELECT id FROM jobs WHERE result_id=? AND status IN ('queued','running')", (key,)):
            raise AppError('文件正在解析，请等待当前任务结束', 409)
        db.safe_path(file['path'])
        db.execute("UPDATE files SET status='processing',error=NULL WHERE id=?", (key,))
        job_id = db.job('pdf', key)
        start_job(job_id, lambda: services.process_pdf(key), key)
        return {'file_id': key, 'job_id': job_id}

    @app.delete('/api/files/{key}')
    async def delete_file(key: str):
        file = db.one('SELECT type FROM files WHERE id=?', (key,), required=True)
        return services.delete_meeting_file(key) if file['type'] == 'txt' else services.delete_pdf(key)

    @app.get('/api/jobs')
    async def jobs():
        return db.all('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 100')

    @app.get('/api/files/{key}/text')
    async def extracted_text(key: str, download: bool = False, paragraph: int | None = Query(None, ge=1), end: int | None = Query(None, ge=1)):
        file, path = services.exported_pdf_text(key)
        from urllib.parse import quote
        if paragraph is not None and not download:
            import html
            paragraphs = pdf_paragraphs(pdf_pages(db.safe_path(file['path']).read_bytes()))
            numbers = [p['number'] for p in paragraphs]
            last = end if end is not None else paragraph
            if paragraph not in numbers or last not in numbers or last < paragraph:
                raise AppError('TXT 段落范围不存在', 404)
            body = []
            for item in paragraphs:
                number = item['number']
                selected = ' class="selected"' if paragraph <= number <= last else ''
                body.append(f'<section id="paragraph-{number}"{selected}><h2>PDF 第 {item["page"]} 页 · TXT 第 {number} 段</h2><pre>' + html.escape(item['text']) + '</pre></section>')
            document = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(file['filename']) + ' · 提取文本</title><style>body{max-width:960px;margin:32px auto;padding:0 20px;color:#172033;font-family:system-ui}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.8 monospace}section{padding:12px 20px;margin:16px 0;border:1px solid #ddd;border-radius:8px;scroll-margin-top:24px}section.selected{background:#fff7d6;border-color:#c99724}h2{font-size:15px;color:#6b560b}</style><body><h1>' + html.escape(file['filename']) + ' · 提取文本</h1><p>黄色标出本次引用范围。编号与下载的 TXT 一致。</p>' + ''.join(body) + '</body></html>'
            return Response(document, media_type='text/html', headers={'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'", 'X-Content-Type-Options': 'nosniff'})
        disposition = 'attachment' if download else 'inline'
        filename = Path(file['filename']).stem + '.extracted.txt'
        return Response(path.read_bytes(), media_type='text/plain', headers={
            'Content-Disposition': disposition + "; filename*=UTF-8''" + quote(filename),
            'X-Content-Type-Options': 'nosniff',
        })

    @app.get('/api/jobs/{key}')
    async def job(key: str):
        return db.one('SELECT * FROM jobs WHERE id=?', (key,), required=True)

    @app.get('/api/meetings')
    async def meetings():
        rows = db.all('SELECT m.*,f.filename FROM meetings m JOIN files f ON f.id=m.file_id ORDER BY m.analyzed_at DESC')
        for row in rows:
            row['analysis'] = json.loads(row.pop('summary_json'))
            row['tasks'] = db.all('SELECT * FROM tasks WHERE meeting_id=?', (row['id'],))
        return rows

    @app.delete('/api/meetings/{key}')
    async def delete_meeting(key: str):
        meeting = db.one('SELECT file_id FROM meetings WHERE id=?', (key,), required=True)
        return services.delete_meeting_file(meeting['file_id'])

    @app.get('/api/tasks')
    async def tasks():
        rows = db.all('SELECT * FROM tasks ORDER BY rowid DESC')
        for row in rows:
            row['email_logs'] = db.all('SELECT recipient,status,error,sent_at FROM email_logs WHERE task_id=?', (row['id'],))
        return rows

    @app.delete('/api/tasks/{key}')
    async def delete_task(key: str):
        return services.delete_task(key)

    @app.patch('/api/tasks/{key}')
    async def update_task(key: str, request: Request):
        payload = await request.json()
        if payload.get('status') not in ('open', 'done'):
            raise AppError('待办状态必须为 open 或 done')
        db.one('SELECT id FROM tasks WHERE id=?', (key,), required=True)
        db.execute('UPDATE tasks SET status=? WHERE id=?', (payload['status'], key))
        return {'id': key, 'status': payload['status']}

    @app.post('/api/tasks/{key}/retry-email')
    async def retry_email(key: str):
        task = db.one('SELECT * FROM tasks WHERE id=?', (key,), required=True)
        if task['email_status'] == 'sending':
            raise AppError('邮件正在发送', 409)
        return await services.send_email(key)

    @app.get('/api/memories')
    async def memories(q: str = '', person: str = '', time: str = '', location: str = '', topic: str = ''):
        sql = 'SELECT * FROM memories WHERE 1=1'
        params = []
        for column, value in [('summary', q), ('person', person), ('time_text', time), ('location', location), ('topic', topic)]:
            if value:
                sql += f' AND {column} LIKE ?'
                params.append('%' + value + '%')
        return db.all(sql + ' ORDER BY updated_at DESC LIMIT 200', params)

    @app.post('/api/memories', status_code=201)
    async def create_memory(data: MemoryInput):
        return await services.create_memory(data)

    @app.delete('/api/memories/{key}')
    async def delete_memory(key: str):
        return services.delete_memory(key)

    @app.post('/api/memories/reindex')
    async def reindex():
        return await services.reindex()

    @app.get('/api/memories/{key}/source')
    async def memory_source(key: str):
        memory = db.one('SELECT * FROM memories WHERE id=?', (key,), required=True)
        if memory['source_type'] == 'manual':
            return Response(memory['evidence'], media_type='text/plain; charset=utf-8', headers={'X-Content-Type-Options': 'nosniff'})
        if memory['source_type'] == 'chat':
            source = db.one('SELECT * FROM messages WHERE id=?', (memory['source_id'],), required=True)
            return Response(source['content'], media_type='text/plain; charset=utf-8')
        meeting = db.one('SELECT file_id FROM meetings WHERE id=?', (memory['source_id'],), required=True)
        return await file_content(meeting['file_id'])

    @app.post('/api/slides', status_code=202)
    async def slides(data: SlidesInput):
        job_id = db.job('slides')
        start_job(job_id, lambda: services.create_slides(data, job_id))
        return {'job_id': job_id}

    @app.get('/api/artifacts')
    async def artifacts():
        return db.all('SELECT id,job_id,filename,mime_type,created_at FROM artifacts ORDER BY created_at DESC')

    @app.delete('/api/artifacts/{key}')
    async def delete_artifact(key: str):
        return services.delete_artifact(key)

    @app.get('/api/artifacts/{key}/download')
    async def download(key: str):
        artifact = db.one('SELECT * FROM artifacts WHERE id=?', (key,), required=True)
        from urllib.parse import quote
        return Response(db.safe_path(artifact['path']).read_bytes(), media_type=artifact['mime_type'], headers={'Content-Disposition': "attachment; filename*=UTF-8''" + quote(artifact['filename'])})

    return app


app = create_app()
