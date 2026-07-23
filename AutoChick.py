# AutoChick.py
from .. import loader, utils
from telethon.tl.types import Message
import asyncio, random, re, logging

logger = logging.getLogger("ChickMod")

@loader.tds
class ChickMod(loader.Module):
    """Автоматизация Курятника"""
    strings = {"name": "ChickMod"}
    EMOJI = "🐤"

    def __init__(self):
        self.task = None
        self.bot_id = 6467105350
        self.tg_id = None

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.task_manager = self.lookup("TaskManagerMod")
        
        me = await client.get_me()
        self.tg_id = me.id

        self.db.set(self.strings["name"], "enabled", False)
        
        if self.db.get(self.strings["name"], "autostart", False):
            logger.info("⚡ Autostarting...")
            await self.start_task()

    async def start_task(self, call=None):
        if self.task and not self.task.done(): return
        await asyncio.sleep(1)
        self.db.set(self.strings["name"], "enabled", True)
        self.task = asyncio.create_task(self.chick_loop())

    async def stop_task(self):
        self.db.set(self.strings["name"], "enabled", False)
        if self.task and not self.task.done(): self.task.cancel()

    async def _get_working_message(self):
        try:
            target_gather = f'chick {self.tg_id} gather'.encode('utf-8')
            target_water = f'chick {self.tg_id} water'.encode('utf-8')
            
            async for msg in self.client.iter_messages(self.bot_id, limit=10):
                if not msg.buttons: continue
                
                has_target_buttons = False
                for row in msg.buttons:
                    for btn in row:
                        if btn.data == target_gather or btn.data == target_water:
                            has_target_buttons = True
                            break
                    if has_target_buttons: break
                
                if has_target_buttons:
                    logger.info(f"Работаю с сообщением {msg.id}")
                    return msg
            
            logger.info("Сообщений нет, отправляю 'Муку'")
            await self.client.send_message(self.bot_id, "Муку")
            await asyncio.sleep(random.uniform(3, 4))
            return (await self.client.get_messages(self.bot_id, limit=1))[0]
        except Exception as e:
            logger.error(f"⚠️ Ошибка поиска сообщения: {e}")
            return None

    async def _refresh_message(self, msg_id):
        try:
            msgs = await self.client.get_messages(self.bot_id, ids=msg_id)
            if msgs: return msgs
            return None
        except Exception: return None

    async def _parse_time(self, text):
        hours = 0
        minutes = 0
        h_match = re.search(r"(\d+)\s*час", text)
        if h_match: hours = int(h_match.group(1))
        m_match = re.search(r"(\d+)\s*минут", text)
        if m_match: minutes = int(m_match.group(1))
        
        if hours == 0 and minutes == 0: return 300 
        return (hours * 3600) + (minutes * 60)

    async def chick_loop(self):
        logger.info("Loop started")
        
        target_gather_data = f'chick {self.tg_id} gather'.encode('utf-8')
        target_water_data = f'chick {self.tg_id} water'.encode('utf-8')
        
        while self.db.get(self.strings["name"], "enabled", False):
            if not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue

            lock_acquired = False
            sleep_duration = 300
            
            try:
                if not await self.task_manager.acquire_lock(self.strings["name"]):
                    await asyncio.sleep(1)
                    continue

                lock_acquired = True
                
                msg = await self._get_working_message()
                if not msg or not msg.buttons:
                    logger.warning("Нету кнопок...")
                    await self.task_manager.release_lock(self.strings["name"])
                    lock_acquired = False
                    await asyncio.sleep(60)
                    continue

                while True:
                    water_btn = None
                    gather_btn = None
                    water_percent = 200
                    found_target_buttons = False

                    for row in msg.buttons:
                        for btn in row:
                            if btn.data == target_water_data:
                                water_btn = btn
                                match = re.search(r"💧\s*(\d+)%", btn.text)
                                if match: water_percent = int(match.group(1))
                                found_target_buttons = True
                            
                            elif btn.data == target_gather_data:
                                gather_btn = btn
                                found_target_buttons = True

                    if not found_target_buttons:
                        logger.warning(f"Кнопки исчезли или протухли")
                        break 

                    # 1. ВОДА
                    if water_btn and water_percent <= 180:
                        logger.info(f"Доливаю воду ({water_percent} -> {water_percent+20}%)")
                        result = await water_btn.click()
                        if result.message:
                            notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                            await self.client.send_message(notify_id, result.message)
                        await asyncio.sleep(random.uniform(1.5, 3))
                        msg = await self._refresh_message(msg.id)
                        if not msg: break
                        continue 

                    # 2. СБОР
                    if not gather_btn:
                        logger.info("Кнопки сбора нет")
                        break

                    btn_text = gather_btn.text.lower()
                    
                    # --- Сценарий: СОБРАТЬ ---
                    if "собрать" in btn_text:
                        await gather_btn.click()
                        
                        try:
                            notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                            await asyncio.sleep(2) 
                            
                            found_log = False
                            async for result_msg in self.client.iter_messages(self.bot_id, limit=3):
                                if "залутал курятник" in result_msg.text:
                                    clean_text = re.sub(r'<[^<]+?>', '', result_msg.text)
                                    
                                    match = re.search(r"\+\s*(\d+)\s*(\S+)\s*(.*)", clean_text)
                                    
                                    if match:
                                        amount = match.group(1)
                                        emoji = match.group(2)
                                        name = match.group(3).strip()
                                        final_text = f"{emoji} +{amount} {name}"
                                        
                                        await self.client.send_message(notify_id, final_text)
                                        found_log = True
                                    
                                    if found_log: break
                                    
                        except Exception as e:
                            logger.error(f"⚠️ Ошибка: {e}")
                            
                        await asyncio.sleep(random.uniform(2, 3))
                        msg = await self._refresh_message(msg.id)
                        if not msg: break
                        continue

                    # --- Сценарий: БАБОЧКА ---
                    elif "🦋" in btn_text:
                        wait_butterfly = 180 + random.uniform(2, 10)
                        logger.info(f"Бабочка! КД {int(wait_butterfly // 60)} мин" + (f" {int(wait_butterfly % 60)} сек" if int(wait_butterfly % 60) > 0 else ""))
                        
                        if lock_acquired:
                            await self.task_manager.release_lock(self.strings["name"])
                            lock_acquired = False
                        
                        await asyncio.sleep(wait_butterfly)
                        
                        if not await self.task_manager.check_schedule(self):
                            break
                        
                        while not await self.task_manager.acquire_lock(self.strings["name"]):
                            await asyncio.sleep(1)
                        lock_acquired = True
                        
                        try:
                            await gather_btn.click()
                            notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                            await self.client.send_message(notify_id, "🦋 -1 бабочка")
                        except Exception:
                            break
                        
                        await asyncio.sleep(random.uniform(2, 3))
                        msg = await self._refresh_message(msg.id)
                        if not msg: break
                        continue

                    # --- Сценарий: ЧАСЫ ---
                    elif "⏰" in btn_text or "минут" in btn_text or "час" in btn_text:
                        seconds_left = await self._parse_time(btn_text)
                        sleep_duration = seconds_left + 60 + random.uniform(1, 10)
                        logger.info(f"КД обнаружено. {int(sleep_duration // 60)} мин" + (f" {int(sleep_duration % 60)} сек" if int(sleep_duration % 60) > 0 else ""))
                        break 

                    else:
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"⚠️ Ошибка: {e}", exc_info=True)
                await asyncio.sleep(60)
            finally:
                if lock_acquired:
                    await self.task_manager.release_lock(self.strings["name"])

            # --- СОН ---
            check_interval = 1800
            if sleep_duration > check_interval:
                logger.info(f"Долгий сон. Буду отправлять 'Муку' каждые 30 мин")
                while sleep_duration > 0:
                    current_sleep = min(sleep_duration, check_interval)
                    await asyncio.sleep(current_sleep)
                    sleep_duration -= current_sleep
                    if sleep_duration > 0:
                        await self._maintenance_water_check(target_water_data)
            else:
                logger.info(f"Сон {int(sleep_duration // 60)} мин" + (f" {int(sleep_duration % 60)} сек" if int(sleep_duration % 60) > 0 else ""))
                await asyncio.sleep(sleep_duration)

        logger.info("Loop stopped")

    async def _maintenance_water_check(self, target_water_data):
        logger.info("Проверка воды...")
        lock_acquired = False
        try:
            while not await self.task_manager.acquire_lock(self.strings["name"]):
                await asyncio.sleep(1)
            
            lock_acquired = True
            
            await self.client.send_message(self.bot_id, "Муку")
            await asyncio.sleep(random.uniform(3, 4))
            
            msgs = await self.client.get_messages(self.bot_id, limit=1)
            if not msgs or not msgs[0].buttons: 
                return
                
            msg = msgs[0]

            while True:
                water_btn = None
                water_percent = 200
                found_water = False
                
                for row in msg.buttons:
                    for btn in row:
                        if btn.data == target_water_data:
                            water_btn = btn
                            found_water = True
                            match = re.search(r"💧\s*(\d+)%", btn.text)
                            if match: water_percent = int(match.group(1))
                            break
                
                if not found_water: break

                if water_btn and water_percent <= 180:
                    logger.info(f"Доливаю воду ({water_percent} -> {water_percent+20}%)")
                    result = await water_btn.click()
                    if result.message:
                        notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                        await self.client.send_message(notify_id, result.message)
                    await asyncio.sleep(random.uniform(1.5, 3))
                    msg = await self._refresh_message(msg.id)
                    if not msg: break
                else:
                    break
        except Exception as e:
            logger.error(f"⚠️ Ошибка: {e}")
        finally:
            if lock_acquired:
                await self.task_manager.release_lock(self.strings["name"])

    async def get_status_text(self):
        enabled = self.db.get(self.strings["name"], "enabled", False)
        return f"{self.EMOJI} {self.strings['name']}: {'✅' if enabled else '❌'}"

    async def render_settings(self, call):
        text = f"<b>{self.EMOJI} Настройки курятника</b>"
        buttons = [
            [{'text': f"🕰️ Случайное время {'✅' if self.db.get(self.strings['name'], 'random_schedule', False) else '❌'}", 
              'callback': self.lookup("ControlPanelMod").toggle_random_schedule, "args": ("chick",)}],
            [{'text': '⬅️ Назад', 'callback': self.lookup("ControlPanelMod").open_module_menu, "args": ("chick",)}]]
        await call.edit(text, reply_markup=buttons)