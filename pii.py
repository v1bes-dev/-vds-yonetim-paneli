# pii.py — LLM'e gitmeden once hassas veriyi maskeler. Amac: telefon, e-posta,
# TC kimlik no gibi veriler modelin context'ine hic girmesin (loglara ve diskteki
# sohbet gecmisine de ham halde yazilmasin).
import re

_TCKN = re.compile(r"(?<!\d)(\d{11})(?!\d)")
_PHONE = re.compile(r"(?<!\d)(0?5\d{2})[\s.-]?(\d{3})[\s.-]?(\d{2})[\s.-]?(\d{2})(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _mask_middle(s: str, keep_start: int = 2, keep_end: int = 2) -> str:
    if len(s) <= keep_start + keep_end:
        return "*" * len(s)
    return s[:keep_start] + "*" * (len(s) - keep_start - keep_end) + s[-keep_end:]


def redact(text: str) -> str:
    if not text:
        return text
    text = _EMAIL.sub(lambda m: _mask_middle(m.group(0), 2, 4), text)
    text = _PHONE.sub(lambda m: _mask_middle("".join(m.groups()), 3, 2), text)
    text = _TCKN.sub(lambda m: _mask_middle(m.group(1), 2, 2), text)
    return text
