"""Detect a private LAN IPv4 and update only LAN access settings. Never print secrets."""
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NETWORKS = tuple(ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def private_ipv4(value):
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return None
    return str(address) if any(address in network for network in NETWORKS) else None


def command_json(*args):
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True, timeout=5)
        return json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def detect_ip():
    override = os.environ.get('CORTEX_LAN_IP', '').strip()
    if override:
        value = private_ipv4(override)
        if not value:
            raise ValueError('CORTEX_LAN_IP 必须是 10.x、172.16–31.x 或 192.168.x 的局域网 IPv4 地址')
        return value
    interfaces = command_json('ip', '-j', '-4', 'addr', 'show', 'scope', 'global')
    candidates = {}
    for interface in interfaces:
        name = interface.get('ifname', '')
        if name.startswith(('lo', 'docker', 'br-', 'veth', 'virbr', 'tun', 'tap', 'tailscale', 'wg')):
            continue
        addresses = [private_ipv4(item.get('local', '')) for item in interface.get('addr_info', [])]
        candidates[name] = [value for value in addresses if value]
    routes = command_json('ip', '-j', '-4', 'route', 'show', 'default')
    for route in sorted(routes, key=lambda item: item.get('metric', 0)):
        addresses = candidates.get(route.get('dev', ''), [])
        if addresses:
            return addresses[0]
    addresses = list(dict.fromkeys(value for group in candidates.values() for value in group))
    if not addresses:
        try:
            result = subprocess.run(['hostname', '-I'], check=True, capture_output=True, text=True, timeout=5)
            addresses = list(dict.fromkeys(value for item in result.stdout.split() if (value := private_ipv4(item))))
        except (OSError, subprocess.SubprocessError):
            pass
    if len(addresses) == 1:
        return addresses[0]
    raise ValueError('无法唯一确定局域网 IP，请执行 CORTEX_LAN_IP=你的局域网IP bash scripts/dev.sh lan')


def configure(path, address):
    address = private_ipv4(address)
    if not address:
        raise ValueError('无效的局域网 IP')
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    values = {
        'AUTH_PUBLIC_ORIGIN': '',
        'AUTH_ALLOWED_HOSTS': json.dumps(['localhost', '127.0.0.1', '::1', address], separators=(',', ':')),
        'CORS_ORIGINS': json.dumps(['http://localhost:3000', 'http://127.0.0.1:3000', f'http://{address}:3000'], separators=(',', ':')),
    }
    for key, value in values.items():
        pattern = rf'^{key}=.*$'
        line = f'{key}={value}'
        text = re.sub(pattern, lambda _: line, text, flags=re.M) if re.search(pattern, text, re.M) else text.rstrip() + '\n' + line + '\n'
    descriptor, temporary = tempfile.mkstemp(prefix='.lan-settings-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        address = detect_ip()
        configure(ROOT / '.env', address)
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
    print(address)
