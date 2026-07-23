# AutoMuz.py
from .. import loader, utils
import asyncio, random, re, logging

logger = logging.getLogger("MuzMod")

@loader.tds
class MuzMod(loader.Module):
    """Автоматизация Тасков"""
    
    strings = {"name": "MuzMod"}
    EMOJI = "💭"

    def __init__(self):
        self.task = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.task_manager = self.lookup("TaskManagerMod")

        if self.db.get(self.strings["name"], "enabled", None) is None:
            self.db.set(self.strings["name"], "enabled", False)
        
        if self.db.get(self.strings["name"], "bot_id", None) is None:
            self.db.set(self.strings["name"], "bot_id", 6467105350)

        if self.db.get(self.strings["name"], "autostart", False):
            logger.info(f"⚡ Autostarting...")
            await self.start_task()

    async def start_task(self, call=None):
        if self.task and not self.task.done():
            return
        self.db.set(self.strings["name"], "enabled", True)
        self.task = asyncio.create_task(self.worker())

    async def stop_task(self):
        self.db.set(self.strings["name"], "enabled", False)
        if self.task and not self.task.done():
            self.task.cancel()
            self.task = None

    async def worker(self):
        logger.info(f"Loop started")
        
        while self.db.get(self.strings["name"], "enabled", False):
            if self.task_manager and not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue

            lock_acquired = False
            try:
                if not await self.task_manager.acquire_lock(self.strings["name"]):
                    await asyncio.sleep(2)
                    continue
                
                lock_acquired = True
                
                bot_id = self.db.get(self.strings["name"], "bot_id")

                await self.client.send_message(bot_id, "Муз")
                await asyncio.sleep(5)
                
                messages = await self.client.get_messages(bot_id, limit=1)
                if not messages:
                    logger.warning(f"Не нашел сообщений от бота")
                    await self.task_manager.release_lock(self.strings["name"])
                    lock_acquired = False
                    await asyncio.sleep(60)
                    continue
                
                msg = messages[0]

                if not msg.buttons:
                    logger.info(f"Сообщение {msg.id} без кнопок. Жду следующую попытку")
                    await self.task_manager.release_lock(self.strings["name"])
                    lock_acquired = False
                    await asyncio.sleep(60)
                    continue

                found_action = False
                
                data_complete = f"ptask_complete {self.tg_id}".encode()
                data_skip_check = f"ptask_skip check {self.tg_id}".encode()

                for row in msg.buttons:
                    for btn in row:
                        if btn.data == data_complete:
                            btn_text = btn.text.lower()
                            
                            if "продать" in btn_text:
                                await btn.click()
                                logger.info(f"Нажал 'Продать'")

                                try:
                                    await asyncio.sleep(2)

                                    last_msgs = await self.client.get_messages(msg.chat_id, limit=5)
                                    target_msg = None
                                    
                                    for m in last_msgs:
                                        if m.text and "выполнил задание" in m.text and "продав" in m.text:
                                            target_msg = m
                                            break

                                    if target_msg:
                                        clean_text = re.sub(r'<[^<]+?>', '', target_msg.text)
                                        
                                        sold_match = re.search(r"продав\s+(\d+).*?(\S+)\s*\n", clean_text)
                                        xp_match = re.search(r"\+\s*(\d+)\s*XP", clean_text)
                                        money_match = re.search(r"\+\s*(\d+)💰", clean_text)

                                        if sold_match and xp_match and money_match:
                                            count = sold_match.group(1)
                                            emoji = sold_match.group(2)
                                            xp = xp_match.group(1)
                                            money = money_match.group(1)

                                            result_text = f"-{count} {emoji}, +{xp} ⭐️, +{money}💰"

                                            notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                                            await self.client.send_message(notify_id, result_text)
                                    else:
                                        logger.warning(f"Не нашел сообщение с результатом в последних 5")

                                except Exception as e:
                                    logger.error(f"⚠️ Ошибка: {e}")

                                found_action = True
                            else:
                                logger.info(f"Ресурсов не хватает. Ищу кнопку пропуска...")
                                await self.click_skip_check(msg, data_skip_check)
                                found_action = True
                        
                        if found_action: break
                    if found_action: break

                if not found_action:
                    logger.warning(f"Не нашел подходящих кнопок")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"⚠️ Ошибка: {e}")
                await asyncio.sleep(60)
            finally:
                if lock_acquired:
                    await self.task_manager.release_lock(self.strings["name"])

            delay = 7200 + random.randint(60, 300)
            logger.info(f"Сплю {delay / 60:.1f} минут...")
            await asyncio.sleep(delay)
        
        logger.info(f"Loop stopped")

    async def click_skip_check(self, msg, data_skip_check):
        clicked_skip = False
        for row in msg.buttons:
            for btn in row:
                if btn.data == data_skip_check:
                    await btn.click()
                    logger.info(f"Нажал 'Пропуск'")
                    clicked_skip = True
                    break
        
        if not clicked_skip:
            logger.warning(f"Не нашел кнопку 'Пропуск'")
            return

        await asyncio.sleep(3)
        msg_updated = await self.client.get_messages(msg.chat_id, ids=msg.id)
        
        pattern = re.compile(rb'ptask_skip true ' + str(self.tg_id).encode() + rb' \d+')
        
        confirmed = False
        if msg_updated and msg_updated.buttons:
            for row in msg_updated.buttons:
                for btn in row:
                    if pattern.match(btn.data):
                        await btn.click()
                        logger.info(f"Подтвердил пропуск")
                        confirmed = True
                        break
                if confirmed: break
        
        if not confirmed:
            logger.warning(f"Не нашел кнопку подтверждения пропуска")

    async def get_status_text(self):
        enabled = self.db.get(self.strings["name"], "enabled", False)
        return f"{self.EMOJI} {self.strings['name']}: {'✅' if enabled else '❌'}"

    async def render_settings(self, call):
        is_random = self.db.get(self.strings["name"], "random_schedule", False)
        random_btn_text = f"🕰️ Случайное время {'✅' if is_random else '❌'}"
        
        buttons = [
            [{'text': random_btn_text, 'callback': self.lookup("ControlPanelMod").toggle_random_schedule, "args": ("muz",)}],
            [{'text': '⬅️ Назад', 'callback': self.lookup("ControlPanelMod").open_module_menu, "args": ("muz",)}]]
        
        await call.edit(f"<b>{self.EMOJI} Настройки тасков</b>", reply_markup=buttons)