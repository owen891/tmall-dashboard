"""collector_credentials 密码的对称加密工具（Fernet）。

存储约定：密码以 ``fernet:<token>`` 前缀写入 app_settings JSON；
无前缀的历史值视为明文，读取时原样返回（等待下次设置保存时自动迁移为密文）。

密钥来源（按优先级）：
  1. 环境变量 ``TMALL_CREDENTIALS_KEY``（Fernet key，44 字符 urlsafe base64）
  2. ``data/.credentials.key`` 文件（首次访问自动生成；.gitignore 已通过
     ``/data/**`` 规则排除，不会入库）

安全说明：Fernet 提供认证加密，密钥与数据库同盘时属于"防误读"级别防护，
并非防窃取；如需更强保护请通过环境变量注入密钥并妥善保管。
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = 'fernet:'
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_KEY_PATH = _PROJECT_ROOT / 'data' / '.credentials.key'


def _load_or_create_key():
    """Return the Fernet key bytes, creating the local key file on first use."""
    configured = os.environ.get('TMALL_CREDENTIALS_KEY')
    if configured:
        return configured.strip().encode('ascii')
    try:
        return _KEY_PATH.read_bytes()
    except OSError:
        pass
    key = Fernet.generate_key()
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_PATH.write_bytes(key)
    return key


def _fernet():
    return Fernet(_load_or_create_key())


def encrypt_password(plain):
    """Encrypt a plaintext password for storage. Empty values stay empty."""
    plain = str(plain or '')
    if not plain:
        return ''
    return _PREFIX + _fernet().encrypt(plain.encode('utf-8')).decode('ascii')


def decrypt_password(stored):
    """Decrypt a stored password. Legacy plaintext (no prefix) passes through.

    Raises ValueError when a fernet-prefixed value cannot be decrypted (missing
    or rotated key), instead of silently returning the ciphertext.
    """
    stored = str(stored or '')
    if not stored:
        return ''
    if not stored.startswith(_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(_PREFIX):].encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError) as error:
        raise ValueError(
            '采集账号密码无法解密：请确认 TMALL_CREDENTIALS_KEY 与写入时一致'
            '（或 data/.credentials.key 未被更换/删除）'
        ) from error
