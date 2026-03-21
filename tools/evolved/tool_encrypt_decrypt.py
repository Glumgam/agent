"""
自動生成ツール: tool_encrypt_decrypt
目的: セキュリティ関連の暗号化機能を提供
情報源: セキュリティ
生成日: 2026-03-19
修正日: 2026-03-19 (key長バグ・encrypt_and_digest・nonce hex長バグ修正)
テスト: ✅ 通過済み
"""
import hashlib
import os
from typing import Optional

try:
    from Crypto.Cipher import AES, DES3
    from Crypto.Random import get_random_bytes
    from Crypto.Util.Padding import pad, unpad
except ImportError:
    pass


def tool_encrypt_decrypt(
    action: str,
    data: str,
    key: Optional[str] = None,
    algorithm: str = "AES",
    rsa_key_length: int = 2048
) -> str:
    """
    暗号化/復号化機能を提供するツール関数。

    Args:
        action: "encrypt" または "decrypt"
        data: 平文 (encrypt時) または _encrypt の戻り値 (decrypt時)
        key: 暗号鍵 (hex文字列, AES=32bytes=64hex, DES3=24bytes=48hex)
             省略時は自動生成した鍵を先頭に付加して返す
        algorithm: "AES" または "DES3"
    """
    try:
        if action == "encrypt":
            return _encrypt(data, key, algorithm)
        elif action == "decrypt":
            return _decrypt(data, key, algorithm)
        else:
            return "ERROR: 不明なアクション。'encrypt' または 'decrypt' を指定してください。"
    except Exception as e:
        return f"ERROR: {str(e)}"


def _generate_aes_key() -> str:
    """AES 256bit(32バイト)鍵をhex文字列で生成する。"""
    # 修正: 32バイト = 64hex文字 (旧: key_length // 8 = 4バイトのバグ)
    return get_random_bytes(32).hex()


def _generate_des3_key() -> str:
    """DES3 192bit(24バイト)鍵をhex文字列で生成する。"""
    return get_random_bytes(24).hex()


def _encrypt(data: str, key: Optional[str], algorithm: str) -> str:
    """データを暗号化する。"""
    auto_key = False
    if not key:
        key = _generate_aes_key() if algorithm == "AES" else _generate_des3_key()
        auto_key = True

    try:
        if algorithm == "AES":
            cipher = AES.new(bytes.fromhex(key), AES.MODE_EAX)
            nonce = cipher.nonce  # 16バイト
            # 修正: encrypt_and_digest() でciphertext と tag を同時取得
            ciphertext, tag = cipher.encrypt_and_digest(data.encode("utf-8"))
            # hex 連結: nonce(32hex) + ciphertext + tag(32hex)
            result = nonce.hex() + ciphertext.hex() + tag.hex()
            prefix = f"KEY:{key}|" if auto_key else ""
            return f"{prefix}AES_ENCRYPTED:{result}"

        elif algorithm == "DES3":
            key_bytes = bytes.fromhex(key)
            cipher = DES3.new(key_bytes, DES3.MODE_CBC, b"\x00" * 8)
            padded = pad(data.encode("utf-8"), DES3.block_size)
            ciphertext = cipher.encrypt(padded)
            prefix = f"KEY:{key}|" if auto_key else ""
            return f"{prefix}DES3_ENCRYPTED:{ciphertext.hex()}"

        else:
            raise ValueError(f"サポートされていないアルゴリズム: {algorithm}")

    except Exception as e:
        raise Exception(f"暗号化エラー: {str(e)}")


def _decrypt(data: str, key: Optional[str], algorithm: str) -> str:
    """データを復号化する。"""
    # KEY:xxx| プレフィックスが付いていれば取り出す
    if data.startswith("KEY:"):
        key_part, data = data.split("|", 1)
        if not key:
            key = key_part[4:]  # "KEY:" の4文字を除いた部分

    if not key:
        raise ValueError("復号化には鍵が必要です")

    try:
        if algorithm == "AES":
            parts = data.split("AES_ENCRYPTED:")
            if len(parts) != 2:
                raise ValueError("暗号化されたデータの形式が正しくありません")
            result = parts[1]
            # 修正: nonce=16バイト=32hex文字, tag=16バイト=32hex文字
            nonce_hex_len = 32
            tag_hex_len   = 32
            nonce      = bytes.fromhex(result[:nonce_hex_len])
            ciphertext = bytes.fromhex(result[nonce_hex_len:-tag_hex_len])
            tag        = bytes.fromhex(result[-tag_hex_len:])
            cipher = AES.new(bytes.fromhex(key), AES.MODE_EAX, nonce=nonce)
            plaintext = cipher.decrypt_and_verify(ciphertext, tag)
            return f"AES_DECRYPTED: {plaintext.decode('utf-8')}"

        elif algorithm == "DES3":
            key_bytes  = bytes.fromhex(key)
            cipher     = DES3.new(key_bytes, DES3.MODE_CBC, b"\x00" * 8)
            ciphertext = bytes.fromhex(data.split("DES3_ENCRYPTED:")[-1])
            plaintext  = unpad(cipher.decrypt(ciphertext), DES3.block_size)
            return f"DES3_DECRYPTED: {plaintext.decode('utf-8')}"

        else:
            raise ValueError(f"サポートされていないアルゴリズム: {algorithm}")

    except Exception as e:
        raise Exception(f"復号化エラー: {str(e)}")


if __name__ == "__main__":
    print("=" * 50)
    print("tool_encrypt_decrypt 動作確認")
    print("=" * 50)

    key = _generate_aes_key()
    print(f"\n生成鍵 (先頭16): {key[:16]}...")

    print("\n1. AES 暗号化")
    enc = tool_encrypt_decrypt("encrypt", "テストメッセージ", key, "AES")
    print(f"  結果: {enc[:60]}...")

    print("\n2. AES 復号化")
    dec = tool_encrypt_decrypt("decrypt", enc, key, "AES")
    print(f"  結果: {dec}")

    print("\n3. 鍵自動生成 (KEY: プレフィックス付き返却)")
    enc2 = tool_encrypt_decrypt("encrypt", "auto-key test", algorithm="AES")
    print(f"  enc: {enc2[:60]}...")
    dec2 = tool_encrypt_decrypt("decrypt", enc2, algorithm="AES")
    print(f"  dec: {dec2}")

    print("\n" + "=" * 50)
    print("動作確認完了")
