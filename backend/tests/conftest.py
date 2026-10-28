"""Keep module-level ASGI app initialization away from the real workspace data."""
import os
from tempfile import TemporaryDirectory

_bootstrap = TemporaryDirectory(prefix='cortex-test-bootstrap-')
os.environ['STORAGE_DIR'] = _bootstrap.name
