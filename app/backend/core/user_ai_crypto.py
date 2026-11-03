"""用户自选 AI 密钥的加密、解密与掩码。

密钥由 APP_AUTH_SECRET 经 SHA-256 派生 Fernet key；缺失密钥时直接报错，
与认证模块保持一致，绝不回退随机密钥。密钥明文不落库、不写日志。
"""

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from core.auth import get_auth_secret

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    secret = get_auth_secret()
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(api_key: str) -> str:
    """加密 API Key，返回可安全落库的密文。"""
    return _fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(token: str) -> str:
    """解密 API Key；密文损坏或密钥变更时抛 ValueError（不回显密文）。"""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError) as exc:
        logger.warning("用户 AI 密钥解密失败，可能密钥已轮换或数据损坏")
        raise ValueError("用户 AI 密钥无法解密，请重新保存配置。") from exc


def mask_api_key(api_key: Optional[str]) -> Optional[str]:
    """掩码展示：保留前 3 与后 4 位，如 sk-****abcd；过短一律 ****。"""
    if not api_key:
        return None
    if len(api_key) < 8:
        return "****"
    return f"{api_key[:3]}****{api_key[-4:]}"
