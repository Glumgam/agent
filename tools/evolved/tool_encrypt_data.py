"""
自動生成ツール: tool_encrypt_data
目的: セキュリティ関連の暗号化機能を提供します。
情報源: セキュリティ
生成日: 2026-03-19
修正日: 2026-03-19 (decrypt API統一、sign/pad バグ修正)
テスト: ✅ 通過済み
"""
import base64
import json
from typing import Optional

try:
    from Crypto.Cipher import AES, PKCS1_OAEP
    from Crypto.PublicKey import RSA
    from Crypto.Random import get_random_bytes
except ImportError:
    pass


def tool_encrypt_data(
    operation: str,
    data: str,
    key: Optional[str] = None,
    rsa_key_size: int = 2048,
    salt: Optional[str] = None
) -> str:
    """
    PyCryptodome 暗号化ツール関数。

    操作:
      encrypt: AES-EAX で data を暗号化。key は32バイトのbase64文字列。
               戻り値: JSON {"operation", "ciphertext", "nonce", "tag"}
      decrypt: encrypt の JSON 出力を data に渡して復号する。key は同じ鍵。
      hash:    SHA256 ハッシュを返す。
      generate_rsa_key: RSA鍵ペアを生成して返す。
    """
    try:
        if operation == "encrypt":
            if not key:
                return "ERROR: key (base64) is required for encryption"
            key_bytes = base64.b64decode(key)
            # AES-EAX はストリームモードなので pad 不要
            cipher = AES.new(key_bytes, AES.MODE_EAX)
            ciphertext, tag = cipher.encrypt_and_digest(data.encode("utf-8"))
            return json.dumps({
                "operation":  "encrypt",
                "ciphertext": base64.b64encode(ciphertext).decode(),
                "nonce":      base64.b64encode(cipher.nonce).decode(),
                "tag":        base64.b64encode(tag).decode(),
            }, indent=2)

        elif operation == "decrypt":
            # data に encrypt の JSON 出力をそのまま渡す
            if not key:
                return "ERROR: key (base64) is required for decryption"
            try:
                enc = json.loads(data)
                ciphertext = base64.b64decode(enc["ciphertext"])
                nonce      = base64.b64decode(enc["nonce"])
                tag        = base64.b64decode(enc["tag"])
            except (json.JSONDecodeError, KeyError):
                return "ERROR: data must be the JSON output from 'encrypt' operation"
            key_bytes = base64.b64decode(key)
            cipher = AES.new(key_bytes, AES.MODE_EAX, nonce=nonce)
            try:
                plaintext = cipher.decrypt_and_verify(ciphertext, tag)
                return f"Decrypted: {plaintext.decode('utf-8')}"
            except ValueError:
                return "ERROR: Decryption failed — MAC check failed (wrong key or corrupted)"

        elif operation == "hash":
            import hashlib
            return f"SHA256: {hashlib.sha256(data.encode()).hexdigest()}"

        elif operation == "generate_rsa_key":
            rsa_key     = RSA.generate(rsa_key_size)
            public_key  = rsa_key.publickey().export_key()
            private_key = rsa_key.export_key()
            return json.dumps({
                "operation":   "generate_rsa_key",
                "key_size":    rsa_key_size,
                "public_key":  base64.b64encode(public_key).decode(),
                "private_key": base64.b64encode(private_key).decode(),
            }, indent=2)

        else:
            return "ERROR: Unknown operation. Supported: encrypt, decrypt, hash, generate_rsa_key"

    except ImportError as e:
        return f"ERROR: Required library not installed - {str(e)}"
    except Exception as e:
        return f"ERROR: Operation failed - {str(e)}"


def generate_aes_key() -> str:
    """32バイト(256bit) AES鍵をbase64文字列で生成する。"""
    return base64.b64encode(get_random_bytes(32)).decode()


if __name__ == "__main__":
    print("=== tool_encrypt_data 動作確認 ===")
    key = generate_aes_key()
    print(f"AES key (先頭16): {key[:16]}...")

    enc = tool_encrypt_data("encrypt", "Hello, Secure World!", key=key)
    print(f"encrypt: {enc[:80]}...")

    dec = tool_encrypt_data("decrypt", enc, key=key)
    print(f"decrypt: {dec}")

    h = tool_encrypt_data("hash", "test data")
    print(f"hash: {h}")
    print("=== 完了 ===")
