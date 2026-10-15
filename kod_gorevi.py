# kod_gorevi.py — WhatsApp'tan "/kod <gorev>" ile gercek bir Claude Code
# oturumu baslatir. ONEMLI: hicbir dosya degistirme/komut calistirma OTOMATIK
# olmaz. Once "plan" modunda calisir (sadece okur, hicbir sey degistirmez),
# planini WhatsApp'a gonderir; kullanici "evet" demeden TEK SATIR kod/komut
# calismaz. Onaydan sonra ayni oturum devam ettirilip plan uygulanir.
import os
import asyncio
import subprocess
from pathlib import Path

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage,
)

PROJE_KLASORU = os.getenv("KOD_GOREVI_KLASORU", str(Path(__file__).parent.resolve()))
MAX_TURNS = int(os.getenv("KOD_GOREVI_MAX_TURN", "20"))
MAX_BUDGET_USD = float(os.getenv("KOD_GOREVI_MAX_USD", "2.0"))

# chat_id -> {"session_id": str, "gorev": str}  (bellekte tutulur; bot yeniden
# baslarsa bekleyen plan kaybolur — bilerek, kalici state karmasikliga sebep olur)
_bekleyen_planlar: dict[str, dict] = {}


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", PROJE_KLASORU, *args], capture_output=True, text=True, timeout=30)


def _git_commit_snapshot(mesaj: str) -> None:
    try:
        _git("add", "-A")
        _git("commit", "-m", mesaj, "--allow-empty")
    except Exception:
        pass


def _git_diff_ozet() -> str:
    try:
        r = _git("diff", "--stat", "HEAD~1", "HEAD")
        return r.stdout.strip() or "(degisiklik yok)"
    except Exception as e:
        return f"(diff alinamadi: {e})"


async def _plan_olustur_async(gorev: str):
    options = ClaudeAgentOptions(
        permission_mode="plan",
        cwd=PROJE_KLASORU,
        max_turns=MAX_TURNS,
        max_budget_usd=MAX_BUDGET_USD,
    )
    plan_metni = None
    session_id = None
    async for msg in query(prompt=gorev, options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, ToolUseBlock) and block.name == "ExitPlanMode":
                    plan_metni = block.input.get("plan", "")
                elif isinstance(block, TextBlock) and plan_metni is None:
                    plan_metni = block.text
        if isinstance(msg, ResultMessage):
            session_id = msg.session_id
            if plan_metni is None:
                plan_metni = msg.result
    return session_id, (plan_metni or "(plan olusturulamadi, tekrar dene)")


async def _plani_uygula_async(session_id: str) -> str:
    options = ClaudeAgentOptions(
        permission_mode="acceptEdits",
        resume=session_id,
        cwd=PROJE_KLASORU,
        max_turns=MAX_TURNS,
        max_budget_usd=MAX_BUDGET_USD,
    )
    sonuc_metni = None
    async for msg in query(prompt="Onaylandi, plani uygula.", options=options):
        if isinstance(msg, ResultMessage):
            sonuc_metni = msg.result
    return sonuc_metni or "(sonuc alinamadi)"


def gorev_plani_iste(chat_id: str, gorev: str) -> str:
    session_id, plan = asyncio.run(_plan_olustur_async(gorev))
    _bekleyen_planlar[chat_id] = {"session_id": session_id, "gorev": gorev}
    return plan


def bekleyen_plan_var_mi(chat_id: str) -> bool:
    return chat_id in _bekleyen_planlar


def plani_onayla(chat_id: str) -> str:
    bekleyen = _bekleyen_planlar.pop(chat_id, None)
    if not bekleyen:
        return "Onaylanacak bir plan yok."
    _git_commit_snapshot(f"[kod_gorevi] onay-oncesi anlik goruntu: {bekleyen['gorev'][:60]}")
    sonuc = asyncio.run(_plani_uygula_async(bekleyen["session_id"]))
    _git_commit_snapshot(f"[kod_gorevi] {bekleyen['gorev'][:60]}")
    return f"{sonuc}\n\nDegisen dosyalar:\n{_git_diff_ozet()}"


def plani_reddet(chat_id: str) -> str:
    if chat_id in _bekleyen_planlar:
        del _bekleyen_planlar[chat_id]
        return "Plan iptal edildi, hicbir degisiklik yapilmadi."
    return "Zaten bekleyen bir plan yok."
