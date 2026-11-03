"""密码哈希：使用标准库 scrypt，避免引入新依赖。

项目未安装 passlib/bcrypt，因此采用 hashlib.scrypt（标准 KDF，非自造加密）。
存储格式 ``scrypt$N$r$p$salt_hex$hash_hex``，便于后续更换参数时不失效。
"""
import hashlib
import hmac
import secrets

_SCHEME = "scrypt"
_N = 2**14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN
    )
    return f"{_SCHEME}${_N}${_R}${_P}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        scheme, n_raw, r_raw, p_raw, salt_hex, hash_hex = encoded.split("$", 5)
        if scheme != _SCHEME:
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
            dklen=len(bytes.fromhex(hash_hex)),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived.hex(), hash_hex)
