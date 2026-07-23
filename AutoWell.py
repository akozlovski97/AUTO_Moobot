# AutoWell.py
from .. import loader, utils
import asyncio, re, time, logging

logger = logging.getLogger("AutoWell")

@loader.tds
class AutoWellMod(loader.Module):
    """Автоматизация Колодца"""
    strings = {"name": "AutoWell"}
    EMOJI = "💧"

    def __init__(self):
        self.task = None
        self.next_run = 0

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.task_manager = self.lookup("TaskManagerMod")

        self.db.set(self.strings["name"], "enabled", False)

        if self.db.get(self.strings["name"], "collect_at", None) is None:
            self.db.set(self.strings["name"], "collect_at", 1179)

        self.cow_id = 6467105350

        if self.db.get(self.strings["name"], "autostart", False):
            logger.info("⚡ Autostarting...")
            await self.start_task()

    async def start_task(self, call=None):
        if self.task and not self.task.done():
            return
        self.db.set(self.strings["name"], "enabled", True)
        self.task = asyncio.create_task(self.autowell_loop())

    async def stop_task(self):
        self.db.set(self.strings["name"], "enabled", False)
        if self.task and not self.task.done():
            self.task.cancel()
            self.task = None

    async def autowell_loop(self):
        logger.info("Loop started")
        while self.db.get(self.strings["name"], "enabled", False):
            if not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue
            try:
                lock_acquired = False
                try:
                    if not await self.task_manager.acquire_lock(self.strings["name"]):
                        await asyncio.sleep(1)
                        continue
                    
                    lock_acquired = True

                    collect_at = self.db.get(self.strings["name"], "collect_at")
                    await self.client.send_message(self.cow_id, "Муко")
                    await asyncio.sleep(3)
                    msg = (await self.client.get_messages(self.cow_id, limit=1))[0]
                    
                    if msg and msg.text and msg.buttons:
                        current_match = re.search(r"💧\s+<b>([\d.,]+)</b>", msg.text)
                        if current_match:
                            current = float(current_match.group(1).replace(",", "."))
                            if current >= collect_at:
                                for row in msg.buttons:
                                    for button in row:
                                        if "забрать" in button.button.text.lower():
                                            await asyncio.sleep(1.5)
                                            await msg.click(data=f"waterhole {self.tg_id} out".encode())
                                            control_panel = self.lookup("ControlPanelMod")
                                            notify_id = await control_panel.get_notify_id()
                                            await self.client.send_message(notify_id, f"💧 +{current} водички")
                                            break
                                    else: continue
                                    break
                    
                except Exception as e:
                    logger.error(f"⚠️ Ошибка: {e}")
                finally:
                    if lock_acquired:
                        await self.task_manager.release_lock(self.strings["name"])

                sleep_duration = 18000
                logger.info(f"КД {sleep_duration / 3600:.1f} часов")
                self.next_run = time.time() + sleep_duration
                await asyncio.sleep(sleep_duration)

            except asyncio.CancelledError:
                break
        
        self.db.set(self.strings["name"], "enabled", False)
        logger.info("Loop stopped")

    async def get_status_text(self):
        enabled = self.db.get(self.strings["name"], "enabled", False)
        return f"{self.EMOJI} {self.strings['name']}: {'✅' if enabled else '❌'}"

    async def render_settings(self, call):
        thresholds = [1, 5, 25, 50, 100, 250, 500, 1000, 1179, 2000]
        buttons = utils.chunks(
            [
                {
                    "text": "без автосбора" if t == 2000 else str(t),
                    "callback": self.set_collect_at,
                    "args": (t,)
                }
                for t in thresholds
            ],
            3
        )

        is_random = self.db.get(self.strings["name"], "random_schedule", False)
        random_btn_text = f"🕰️ Случайное время {'✅' if is_random else '❌'}"
        buttons.append([{'text': random_btn_text, 'callback': self.lookup("ControlPanelMod").toggle_random_schedule, "args": ("well",)}])

        buttons.append([{'text': '⬅️ Назад', 'callback': self.lookup("ControlPanelMod").open_module_menu, "args": ("well",)}])

        collect_at = self.db.get(self.strings["name"], "collect_at")
        if collect_at == 2000:
            collect_text = "без автосбора"
        else:
            collect_text = f"{collect_at} литров"

        text = (
            f"<b>{self.EMOJI} Настройки колодца</b>\n\n"
            f"<b>🧤 Собираем при:</b> <code>{collect_text}</code>")
        await call.edit(text=text, reply_markup=buttons)

    async def set_collect_at(self, call, value: int):
        self.db.set(self.strings["name"], "collect_at", value)
        if value == 2000:
            value = "без автосбора"
        await call.answer(f"✅ Порог изменён на: {value}")
        await self.render_settings(call)