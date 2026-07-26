import asyncio
import importlib
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
os.environ["DATABASE_PATH"] = str(ROOT / "data" / "debug_reg.db")
os.environ["ADMIN_TELEGRAM_IDS"] = ""
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "x")
os.environ.setdefault("OPENAI_API_KEY", "x")
Path(os.environ["DATABASE_PATH"]).unlink(missing_ok=True)
sys.path.insert(0, str(ROOT))

from app.settings import get_settings

get_settings.cache_clear()
import app.config

importlib.reload(app.config)

from app.db.connection import get_connection, init_db
from app.handlers.chat import chat
from app.repositories.conversation_repository import upsert_user
from app.services.registration_state import registration_snapshot


class U:
    id = 880002
    username = "f"
    full_name = "F"


class M:
    def __init__(self, t: str):
        self.text = t
        self.reply_text = AsyncMock()


class Up:
    def __init__(self, t: str):
        self.effective_user = U()
        self.message = M(t)


class Ctx:
    def __init__(self):
        self.user_data = {}


async def run() -> None:
    init_db()
    uid = upsert_user(880002, "f", "F")
    from app.handlers.location import handle_location_registration_text
    from app.repositories.patient_profile_repository import get_or_create_patient_profile
    from app.services.registration_state import start_registration

    ctx = Ctx()
    print("direct start_registration", registration_snapshot(ctx))
    start_registration(ctx)
    print("after start_registration", registration_snapshot(ctx), ctx.user_data)

    profile = get_or_create_patient_profile(uid)
    up = Up("O'zbekiston")
    result = await handle_location_registration_text(
        up, ctx, user_id=uid, conversation_id=1, patient_profile=profile
    )
    ctx = Ctx()
    texts = ["O'zbekiston", "Surxandaryo", "Jarqorgon"]
    with patch("app.handlers.chat.ask_ai", MagicMock(return_value="ai")):
        for text in texts:
            up = Up(text)
            await chat(up, ctx)
            print("text", text)
            print("snapshot", registration_snapshot(ctx))
            with get_connection() as c:
                row = c.execute(
                    "select user_id, country, region, district from patient_profiles where user_id=?",
                    (uid,),
                ).fetchone()
                print("profile", dict(row) if row else None)
            call = up.message.reply_text.await_args
            print("reply", call.args[0] if call else None)
            print("---")


asyncio.run(run())
