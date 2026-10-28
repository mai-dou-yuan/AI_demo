"""Download official PDF fixtures; verify a text layer without uploading them."""
import hashlib
import json
import os
from pathlib import Path

import httpx
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'samples' / 'knowledge'


def inspect_pdf(data):
    if not data.lstrip().startswith(b'%PDF-'):
        raise ValueError('返回内容不是 PDF，可能是网站拦截页面')
    with pymupdf.open(stream=data, filetype='pdf') as doc:
        if doc.needs_pass:
            raise ValueError('PDF 已加密')
        lengths = [len(page.get_text().strip()) for page in doc]
        if not sum(lengths):
            raise ValueError('PDF 无可提取文字，当前项目未启用 OCR')
        return {'pages': len(doc), 'page_text_lengths': lengths, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    sources = json.loads((TARGET / 'sources.json').read_text())
    proxy = os.environ.get('PDF_DOWNLOAD_PROXY') or None
    reports = []
    failures = 0
    # Ignore inherited ALL_PROXY; use an explicit HTTP proxy only when requested.
    with httpx.Client(trust_env=False, proxy=proxy, follow_redirects=True, timeout=httpx.Timeout(30, connect=8)) as client:
        for item in sources:
            target = TARGET / item['filename']
            try:
                if target.exists():
                    data = target.read_bytes()
                else:
                    chunks = []
                    size = 0
                    with client.stream('GET', item['url']) as response:
                        response.raise_for_status()
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > 20 * 1024 * 1024:
                                raise ValueError('文件超过项目的默认 20 MB 上传限制')
                            chunks.append(chunk)
                    data = b''.join(chunks)
                metadata = inspect_pdf(data)
                if not target.exists():
                    target.write_bytes(data)
                reports.append({**item, **metadata, 'status': 'ready'})
                print(f"成功：{item['filename']} · {metadata['pages']} 页 · {metadata['bytes'] / 1024:.1f} KB · 有文字层", flush=True)
            except Exception as exc:
                failures += 1
                reports.append({**item, 'status': 'failed', 'error_type': type(exc).__name__})
                print(f"失败：{item['filename']}（{type(exc).__name__}）；可直接从 sources.json 中的官方链接下载", flush=True)
    (TARGET / 'download-report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    print('下载不会自动上传到知识库，也不会调用 Embedding。')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
