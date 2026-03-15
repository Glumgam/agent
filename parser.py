import json
import json5
import re
from typing import Optional, Dict


def _fix_unescaped_newlines(text: str) -> str:
    """
    JSON文字列内部の未エスケープ改行を \\n に変換
    """

    result = []
    in_string = False
    escape = False

    for ch in text:

        if escape:
            result.append(ch)
            escape = False
            continue

        if ch == "\\":
            result.append(ch)
            escape = True
            continue

        if ch == '"':
            in_string = not in_string
            result.append(ch)
            continue

        if in_string and ch == "\n":
            result.append("\\n")
            continue

        if in_string and ch == "\r":
            continue

        result.append(ch)

    return "".join(result)


def _unescape_json_string(raw: str) -> str:
    """
    JSON文字列のエスケープを戻す
    """

    return (
        raw
        .replace("\\\\", "\x00BS\x00")
        .replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\/", "/")
        .replace("\x00BS\x00", "\\")
    )


def _extract_fields_fallback(text: str) -> Optional[Dict]:
    """
    JSONが壊れている場合の最終フォールバック
    """

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    snippet = text[start:end + 1]

    result = {}

    for field in ("thought", "tool", "path", "command", "old", "new"):

        pattern = rf'"{field}"\s*:\s*"((?:[^"\\]|\\.)*)"'

        m = re.search(pattern, snippet)

        if m:

            try:
                result[field] = json.loads(f'"{m.group(1)}"')
            except Exception:
                result[field] = m.group(1)

    if "tool" not in result:
        return None

    content_match = re.search(r'"content"\s*:\s*"', snippet)

    if content_match:

        start_pos = content_match.end()

        # content以降
        remainder = snippet[start_pos:]

        depth = 0
        end_index = None

        for i, c in enumerate(remainder):

            if c == '"' and (i == 0 or remainder[i-1] != "\\"):

                end_index = i
                break

        if end_index:

            raw = remainder[:end_index]

            result["content"] = _unescape_json_string(raw)

    return result


def _extract_json_objects(text: str):
    """
    テキストからJSONオブジェクト候補を抽出
    """

    stack = []
    start = None

    for i, ch in enumerate(text):

        if ch == "{":

            if start is None:
                start = i

            stack.append("{")

        elif ch == "}":

            if stack:
                stack.pop()

                if not stack and start is not None:

                    yield text[start:i + 1]

                    start = None


def extract_json(text: str) -> Optional[Dict]:
    """
    LLMレスポンスからJSONを安全に抽出
    """

    if not text:
        return None

    # Markdown block抽出
    blocks = re.findall(
        r"```(?:json)?\s*([\s\S]*?)\s*```",
        text,
        re.IGNORECASE
    )

    candidates = blocks + [text]

    for cand in candidates:

        cand = cand.strip()

        if not cand:
            continue

        fixed = _fix_unescaped_newlines(cand)

        for source in (cand, fixed):

            # 直接パース
            for loader in (json.loads, json5.loads):

                try:

                    obj = loader(source)

                    if isinstance(obj, dict) and "tool" in obj:
                        return obj

                except Exception:
                    pass

            # JSONオブジェクト探索
            for snippet in _extract_json_objects(source):

                for loader in (json.loads, json5.loads):

                    try:

                        obj = loader(snippet)

                        if isinstance(obj, dict) and "tool" in obj:
                            return obj

                    except Exception:
                        pass

            # fallback
            fallback = _extract_fields_fallback(source)

            if fallback:
                return fallback

    return None
