# grounding.py — ciktinin "halisünasyon" olup olmadigini kontrol eder.
# GERCEK savunma, modelin veritabanina SADECE db.py'deki parametreli
# fonksiyonlarla erismesidir; bu dosya ek bir kontrol katmanidir: model bu
# turda hicbir aractan gelmeyen bir talep (#id) numarasi soyluyorsa, bu
# uydurma veridir ve yanit guvenli bir mesajla degistirilir.
import re

_TALEP_ID = re.compile(r"#(\d+)")

SAFE_FALLBACK = "Bu bilgiyi dogrulayamadim. Talep numarasini tekrar kontrol edebilir misiniz?"


def check_grounded(ai_text: str, tool_outputs: list[str]) -> tuple[bool, str]:
    mentioned = set(_TALEP_ID.findall(ai_text))
    if not mentioned:
        return True, ai_text
    combined_outputs = "\n".join(tool_outputs)
    grounded_ids = set(_TALEP_ID.findall(combined_outputs))
    hallucinated = mentioned - grounded_ids
    if hallucinated:
        return False, SAFE_FALLBACK
    return True, ai_text
