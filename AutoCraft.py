# AutoCraft.py
from .. import utils, loader
import asyncio, re, random, logging

logger = logging.getLogger("CraftMod")

@loader.tds
class CraftMod(loader.Module):
    """Автоматизация Крафта"""
    strings = {"name": "CraftMod"}
    EMOJI = "🔥"

    def __init__(self):
        self.task = None
        self.all_items = {}
        self.chat_id = 6467105350

    async def client_ready(self, client, db):
        self.db = db
        self.client = client
        self.task_manager = self.lookup("TaskManagerMod")

        self.db.set(self.strings["name"], "enabled", False)

        if self.db.get(self.strings["name"], "item", None) is None:
            self.db.set(self.strings["name"], "item", "🧈 масло")
        if self.db.get(self.strings["name"], "quantity", None) is None:
            self.db.set(self.strings["name"], "quantity", 1)
        
        self.all_items = {
            "🧈": "масло", "🍚": "творог", "🧀": "сыр", "🧇": "вафля", "🍦": "мороженка", "🍨": "холодок", 
            "🍪": "печенье", "🥠": "куки", "🍰": "тортик", "🥮": "медовик", "🍼": "молоко+", "🍩": "пончик", 
            "🍫": "шоколад", "🍯": "мёд", "🥣": "мука", "🍞": "хлеб", "🥫": "томат", "🍿": "жопкорн", "🍟": "фришка", 
            "🍔": "бургер", "🥪": "бутер", "🍺": "пиво", "🥨": "крендель", "🥧": "пирог", "🍣": "суши", "🍲": "супчик", 
            "🍵": "холи-суп", "🥗": "сыросалат", "🥦": "брокколи", "🥤": "милк-шейк", "🧃": "дерьмосок", 
            "🍳": "яичница", "🍕": "сыропицца", "💊": "табл", "🩹": "липучка", "🥡": "мегабокс"}

        if self.db.get(self.strings["name"], "autostart", False):
            logger.info("⚡ Autostarting...")
            await self.start_task()
    
    async def start_task(self, call=None):
        if self.task and not self.task.done(): return
        await asyncio.sleep(6)
        self.db.set(self.strings["name"], "enabled", True)
        self.task = asyncio.create_task(self.craft_loop())

    async def stop_task(self):
        self.db.set(self.strings["name"], "enabled", False)
        if self.task and not self.task.done(): self.task.cancel()

    async def process_messages(self, target_text, button_text, button_or_text):
        async for msg in self.client.iter_messages(self.chat_id, limit=2):
            if target_text in msg.text and msg.buttons:
                for row in msg.buttons:
                    for button in row:
                        if button.text == button_or_text or button.text == button_text:
                            await asyncio.sleep(random.uniform(1, 2.5))
                            await button.click()
                            await asyncio.sleep(random.uniform(1, 2.5))
                            return msg
        return None

    async def craft_loop(self):
        logger.info("Loop started")
        
        button_craft = "🔥 скрафтить"
        button_claim = "👋🏻 забрать"
        
        while self.db.get(self.strings["name"], "enabled", False):
            if not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue

            if not await self.task_manager.acquire_lock(self.strings["name"]):
                await asyncio.sleep(1)
                continue

            try:
                # 1. ШАГ: Пишем "Мув"
                await self.client.send_message(self.chat_id, "Мув")
                await asyncio.sleep(random.uniform(1.5, 3))

                msgs = await self.client.get_messages(self.chat_id, limit=3)
                menu_msg = next((m for m in msgs if "Твой верстак" in (m.text or "")), None)

                if not menu_msg:
                    continue

                has_claim = False
                if menu_msg.buttons:
                    for row in menu_msg.buttons:
                        for btn in row:
                            if btn.text == button_claim:
                                has_claim = True
                                break
                
                # 2. ШАГ: Проверка Кулдауна (ЕСЛИ нет кнопки "Забрать")
                if not has_claim and "⏱" in menu_msg.text:
                    cooldown_match = re.search(r'(?:(\d+)\sмин|(\d+)\sсек)', menu_msg.text)
                    if cooldown_match:
                        minutes = int(cooldown_match.group(1) or 0)
                        seconds = int(cooldown_match.group(2) or 0)
                        
                        cooldown_time = 0
                        if minutes > 0:
                            cooldown_time = ((minutes + 1) * 60) + random.randint(2, 10)
                        else:
                            cooldown_time = seconds + random.randint(2, 10)
                        
                        logger.info(f"КД обнаружено. {int(cooldown_time // 60)} мин" + (f" {int(cooldown_time % 60)} сек" if int(cooldown_time % 60) > 0 else ""))
                        await self.task_manager.release_lock(self.strings["name"])
                        await asyncio.sleep(cooldown_time)
                        continue

                # 3. ШАГ: Забрать (если доступно)
                if has_claim:
                    await menu_msg.click(text=button_claim)
                    await asyncio.sleep(random.uniform(1, 2.5))

                    async for res_msg in self.client.iter_messages(self.chat_id, limit=2):
                        if "взял и скрафтил" in (res_msg.text or "") or "взяла и скрафтила" in (res_msg.text or ""):
                            clean_text = re.sub(r'<.*?>', '', res_msg.text)
                            resource_match = re.search(r'\+\s*(\d+)\s*(\S+)\s*(.*)', clean_text)
                            exp_match = re.search(r'⭐️\s*([\d.кk]+)\s*опыта', clean_text)
                            parts = []
                            if resource_match: parts.append(f"{resource_match.group(2)} +{resource_match.group(1)} {resource_match.group(3).strip()}")
                            if exp_match: parts.append(f"⭐️ +{exp_match.group(1)} опыта")
                            if parts:
                                try:
                                    notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                                    await self.client.send_message(notify_id, ", ".join(parts))
                                except: pass
                            break
                    
                    menu_msg = await self.client.get_messages(self.chat_id, ids=menu_msg.id)

                # 4. ШАГ: Крафт
                has_craft = False
                if menu_msg and menu_msg.buttons:
                    for row in menu_msg.buttons:
                        for btn in row:
                            if btn.text == button_craft:
                                has_craft = True
                                break
                
                if has_craft:
                    await menu_msg.click(text=button_craft)
                    await asyncio.sleep(random.uniform(1, 2.5))
                    
                    menu_msg = await self.client.get_messages(self.chat_id, ids=menu_msg.id)
                    target_item = self.db.get(self.strings["name"], "item")
                    target_btn_text = target_item.split(" ")[0]
                    quantity = self.db.get(self.strings["name"], "quantity")
                    
                    item_found = False
                    if menu_msg and menu_msg.buttons:
                        for row in menu_msg.buttons:
                            for btn in row:
                                if btn.text == target_btn_text:
                                    await asyncio.sleep(random.uniform(1, 2.5))
                                    await btn.click()
                                    await asyncio.sleep(random.uniform(1, 2.5))
                                    await menu_msg.reply(str(quantity))
                                    item_found = True
                                    
                                    
                                    await asyncio.sleep(random.uniform(3, 5))
                                    
                                    new_msgs = await self.client.get_messages(self.chat_id, limit=3)
                                    timer_msg = next((m for m in new_msgs if "⏱" in (m.text or "")), None)
                                    
                                    if timer_msg:
                                        cooldown_match = re.search(r'(?:(\d+)\sмин|(\d+)\sсек)', timer_msg.text)
                                        if cooldown_match:
                                            minutes = int(cooldown_match.group(1) or 0)
                                            seconds = int(cooldown_match.group(2) or 0)
                                            
                                            wait_time = 0
                                            if minutes > 0:
                                                wait_time = ((minutes + 1) * 60) + random.randint(5, 15)
                                            else:
                                                wait_time = seconds + random.randint(5, 15)
                                            
                                            logger.info(f"КД обнаружено. {int(wait_time // 60)} мин" + (f" {int(wait_time % 60)} сек" if int(wait_time % 60) > 0 else ""))
                                            await self.task_manager.release_lock(self.strings["name"])
                                            await asyncio.sleep(wait_time)
                                            continue 
                                    break
                            if item_found: break
                    
                    if not item_found and "🔥" in getattr(menu_msg, "text", ""):
                        await self.client.send_message("me", f"<b>🔥 Крафт:</b> Предмет <code>{target_item}</code> не найден! Стоп.")
                        await self.stop_task()

            except Exception as e:
                logger.error(f"⚠️ Ошибка: {e}", exc_info=True)
                await asyncio.sleep(60)
            
            finally:
                await self.task_manager.release_lock(self.strings["name"])
                if self.db.get(self.strings["name"], "enabled", False):
                    await asyncio.sleep(random.uniform(2, 4))

        logger.info("Loop stopped")

    async def get_status_text(self):
        enabled = self.db.get(self.strings["name"], "enabled", False)
        return f"{self.EMOJI} {self.strings['name']}: {'✅' if enabled else '❌'}"
    
    async def render_settings(self, call):
        item = self.db.get(self.strings["name"], "item")
        quantity = self.db.get(self.strings["name"], "quantity")
        text = (
            f"<b>{self.EMOJI} Настройки крафта</b>\n\n"
            f"🧤 Крафтим: <code>{item}</code>\n"
            f"📦 Количество: <code>{quantity}</code>")

        is_random = self.db.get(self.strings["name"], "random_schedule", False)
        random_btn_text = f"🕰️ Случайное время {'✅' if is_random else '❌'}"

        buttons = [
            [{'text': '🧤 Предмет', 'callback': self.show_items}, {'text': '📦 Количество', 'callback': self.show_quantity}],
            [{'text': random_btn_text, 'callback': self.lookup("ControlPanelMod").toggle_random_schedule, "args": ("craft",)}],
            [{'text': '⬅️ Назад', 'callback': self.lookup("ControlPanelMod").open_module_menu, "args": ("craft",)}]]
        await call.edit(text, reply_markup=buttons)

    async def show_items(self, call):
        buttons = utils.chunks([{'text': emoji, 'callback': self.item_selected, "args": (emoji,)} for emoji in self.all_items.keys()], 5)
        buttons.append([{'text': '⬅️ Назад', 'callback': self.render_settings}])
        await call.edit("<b>🔍 Выберите предмет для крафта:</b>", reply_markup=buttons)

    async def item_selected(self, call, selected_emoji):
        text = self.all_items[selected_emoji]
        item_str = f"{selected_emoji} {text}"
        self.db.set(self.strings["name"], "item", item_str)
        await call.answer(f"✅ Крафт изменен на: {item_str}")
        await self.render_settings(call)
    
    async def show_quantity(self, call):
        quantities = [1, 2, 3, 4, 5, 10, 25, 50]
        buttons = utils.chunks([{'text': str(q), 'callback': self.set_quantity, "args": (q,)} for q in quantities], 4)
        buttons.append([{'text': '⬅️ Назад', 'callback': self.render_settings}])
        await call.edit("<b>📦 Выберите количество для крафта:</b>", reply_markup=buttons)

    async def set_quantity(self, call, quantity):
        self.db.set(self.strings["name"], "quantity", quantity)
        await call.answer(f"✅ Количество изменено на: {quantity}")
        await self.render_settings(call)