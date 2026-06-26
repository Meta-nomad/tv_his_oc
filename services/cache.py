import json
import time
import threading
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / '_cache'


class Cache:
    def __init__(self):
        CACHE_DIR.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self._memory: dict[str, dict] = {}

    def _get_path(self, key: str) -> Path:
        safe = key.replace('/', '_').replace(':', '_').replace(' ', '_')
        return CACHE_DIR / f'{safe}.json'

    def get(self, key: str):
        with self._lock:
            if key in self._memory:
                entry = self._memory[key]
                if entry['expires'] > time.time():
                    return entry['value']
                del self._memory[key]

        path = self._get_path(key)
        if not path.exists():
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                entry = json.load(f)
            if entry['expires'] > time.time():
                with self._lock:
                    self._memory[key] = entry
                return entry['value']
            path.unlink(missing_ok=True)
        except (json.JSONDecodeError, OSError):
            pass
        return None

    def set(self, key: str, value, ttl: int = 86400):
        entry = {
            'value': value,
            'expires': time.time() + ttl,
            'created': time.time(),
        }
        with self._lock:
            self._memory[key] = entry
        path = self._get_path(key)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(entry, f)
        except OSError:
            pass

    def clear(self):
        with self._lock:
            self._memory.clear()
        for f in CACHE_DIR.glob('*.json'):
            f.unlink(missing_ok=True)
