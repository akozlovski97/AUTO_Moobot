# AutoGryadka.py
from .. import loader, utils
import asyncio, random, re, logging

logger = logging.getLogger("GryadkaMod")

@loader.tds
class GryadkaMod(loader.Module):
    """Автоматизация Грядок"""
    strings = {"name": "GryadkaMod"}
    EMOJI = "🧑‍🌾"
    
    def __init__(self):
        self.task = None
        self.counter = {}
        self.all_items = {"🥔": "картошка &", "🥬": "капуста &", "🌾": "пшеница &", "🍅": "помидор &", "🌽": "кукуруза &"}

    async def client_ready(self, client, db):
        self.db = db
        self.client = client
        self.task_manager = self.lookup("TaskManagerMod")
        self.chat_id = 6770881933

        self.db.set(self.strings["name"], "enabled", False)

        if self.db.get(self.strings["name"], "item", None) is None:
            self.db.set(self.strings["name"], "item", "пшеница &")

        if self.db.get(self.strings["name"], "autostart", False):
            logger.info("⚡ Autostarting...")
            await self.start_task()
            
    async def start_task(self, call=None):
        if self.task and not self.task.done(): return
        await asyncio.sleep(2)
        self.db.set(self.strings["name"], "enabled", True)
        self.task = asyncio.create_task(self.gryadka_loop())

    async def stop_task(self):
        self.db.set(self.strings["name"], "enabled", False)
        if self.task and not self.task.done(): self.task.cancel()

    async def delayed_message(self):
        await asyncio.sleep(random.uniform(2400, 2500)) 

        create_gryadka = "🌞 Сонячна  ⏰"
        self.counter[create_gryadka] = 0 
        try:
            await self.client.send_message(self.chat_id, "Муг")
            await asyncio.sleep(random.uniform(3, 4)) 
            get_create_gryadka = (await self.client.get_messages(self.chat_id, limit=1))[0]
            item = self.db.get(self.strings["name"], "item")

            for row in get_create_gryadka.buttons:
                for button in row:
                    if button.button.text != create_gryadka:
                        self.counter[create_gryadka] += 1
                        continue
                    
                    await asyncio.sleep(random.uniform(1.5, 2)) 
                    await get_create_gryadka.click(data=f'c_gryad {self.tg_id} g_open {self.counter[create_gryadka]}'.encode())
                    
                    try:
                        await asyncio.sleep(random.uniform(1.5, 2))
                        random_zvezda = random.randrange(0, 8)
                        await get_create_gryadka.click(data=f'c_gryad {self.tg_id} g_ch1 {self.counter[create_gryadka]} {random_zvezda}'.encode())
                        await asyncio.sleep(random.uniform(1.5, 2))  
                        await get_create_gryadka.click(data=f'c_gryad {self.tg_id} g_all {self.counter[create_gryadka]} {random_zvezda}'.encode())
                        await asyncio.sleep(random.uniform(1.5, 2)) 
                        await get_create_gryadka.click(data=f'c_gryad {self.tg_id} g_ch2 {self.counter[create_gryadka]} {random_zvezda} {item}'.encode())
                        await asyncio.sleep(random.uniform(1.5, 2))
                        await get_create_gryadka.click(data=f'c_gryad {self.tg_id} main'.encode())
                        self.counter[create_gryadka] += 1
                    except Exception as e:
                        await self.client.send_message("me", f"🚫 Ошибка: грядка еще не дозрела <b>'🌞 Сонячна  ⏰'</b>\n<code>{e}</code>")
                    break
                else:
                    continue
                break
        except Exception as e:
            await self.client.send_message("me", f"🚫 Ошибка: открытие <b>'🌞 Сонячна  ⏰'</b>\n<code>{e}</code>")

    async def gryadka_loop(self):
        logger.info("Loop started")
        
        button_text_1 = "🌞 Сонячна 💗 ок"
        button_text_2 = r"🌞 Сонячна ⌛️ \d+%"
        button_text_3 = "🌞 Сонячна"

        while self.db.get(self.strings["name"], "enabled", False):
            notify_id = await self.lookup("ControlPanelMod").get_notify_id()
            if not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue
            try:
                item = self.db.get(self.strings["name"], "item")
                self.counter = {button_text_1: 0, button_text_2: 0, button_text_3: 0}

                # --- БЛОК 1: СБОР УРОЖАЯ И РЕМОНТ ---
                lock_acquired = False
                try:
                    if not await self.task_manager.acquire_lock(self.strings["name"]) or await self.task_manager.is_well_soon():
                        await asyncio.sleep(1)
                        continue
                    lock_acquired = True
                    await self.client.send_message(self.chat_id, "Муг")
                    await asyncio.sleep(random.uniform(3, 4))
                    get_mug1 = (await self.client.get_messages(self.chat_id, limit=1))[0]

                    for row in get_mug1.buttons:
                        for button in row:
                            if button.button.text != button_text_1:
                                self.counter[button_text_1] += 1
                                continue
                            
                            await get_mug1.click(data=f'c_gryad {self.tg_id} g_open {self.counter[button_text_1]}'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2))
                            await get_mug1.click(data=f'c_gryad {self.tg_id} gather {self.counter[button_text_1]}'.encode())
                            await asyncio.sleep(random.uniform(3, 4))
                            
                            get_broken = await self.client.get_messages(self.chat_id, limit=6)
                            found = any(re.search(r"😓 ", msg.text) for msg in get_broken)
                            
                            if found:
                                for msg in get_broken:
                                    if msg.reply_markup and hasattr(msg.reply_markup, "rows"):
                                        await msg.click(data=f'yard {self.tg_id} check грядочки'.encode())
                                        await asyncio.sleep(random.uniform(1.5, 2)) 
                                        await msg.click(data=f'c_gryad {self.tg_id} dig_main'.encode())
                                        await asyncio.sleep(random.uniform(1.5, 2)) 
                                        await msg.click(data=f'c_gryad {self.tg_id} dig_view sun'.encode())
                                        await asyncio.sleep(random.uniform(1.5, 2)) 
                                        await msg.click(data=f'c_gryad {self.tg_id} dig_craft sun'.encode())
                                        asyncio.create_task(self.delayed_message())
                                        break
                                break
                            else:
                                await get_mug1.click(data=f'c_gryad {self.tg_id} main'.encode())
                                await asyncio.sleep(random.uniform(1.5, 2)) 
                            
                            self.counter[button_text_1] += 1
                            break
                        else: continue
                except Exception as e:
                    await self.client.send_message("me", f"🚫 Ошибка в сборе/ремонте <b>'{button_text_1}'</b>\n<code>{e}</code>")
                finally:
                    if lock_acquired:
                        await self.task_manager.release_lock(self.strings["name"])

                try:
                    await asyncio.sleep(2) 
                    answer_message = (await self.client.get_messages(self.chat_id, limit=1))[0]

                    match = re.search(r"\+\s*.*?(\d+)\s*(.+)", answer_message.text)
                    if match:
                        amount = match.group(1)
                        item_info = re.sub('<[^<]+?>', '', match.group(2)).strip()
                        
                        parts = item_info.split()
                        emoji = parts[0]
                        name = " ".join(parts[1:])
                        
                        notification_text = f"{emoji} +{amount} {name}"
                        await self.client.send_message(notify_id, notification_text)
                except Exception:
                    pass

                # --- БЛОК 2: ЗАСЕВАНИЕ ГРЯДОК ---
                lock_acquired = False
                sleep_after_plant = random.uniform(1080, 1100)
                try:
                    if not await self.task_manager.acquire_lock(self.strings["name"]) or await self.task_manager.is_well_soon():
                        await asyncio.sleep(1)
                        continue
                    lock_acquired = True
                    await self.client.send_message(self.chat_id, "Муг")
                    await asyncio.sleep(random.uniform(3, 4))
                    get_mug3 = (await self.client.get_messages(self.chat_id, limit=1))[0]

                    for row in get_mug3.buttons:
                        for button in row:
                            if button.button.text != button_text_3:
                                self.counter[button_text_3] += 1
                                continue
                            
                            await get_mug3.click(data=f'c_gryad {self.tg_id} g_open {self.counter[button_text_3]}'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2))
                            random_zvezda = random.randrange(0, 8)
                            await get_mug3.click(data=f'c_gryad {self.tg_id} g_ch1 {self.counter[button_text_3]} {random_zvezda}'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2))  
                            await get_mug3.click(data=f'c_gryad {self.tg_id} g_all {self.counter[button_text_3]} {random_zvezda}'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2)) 
                            await get_mug3.click(data=f'c_gryad {self.tg_id} g_ch2 {self.counter[button_text_3]} {random_zvezda} {item}'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2)) 
                            await get_mug3.click(data=f'c_gryad {self.tg_id} g_water {self.counter[button_text_3]}'.encode())
                            await self.client.send_message(notify_id, "💧 -1 водичка")
                            await asyncio.sleep(random.uniform(1.5, 2))  
                            await get_mug3.click(data=f'c_gryad {self.tg_id} main'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2)) 
                            self.counter[button_text_3] += 1
                            break
                        else: continue
                except Exception as e:
                    await self.client.send_message("me", f"🚫 Ошибка в засаживании <b>'{button_text_3}'</b>\n<code>{e}</code>")
                finally:
                    if lock_acquired:
                        await self.task_manager.release_lock(self.strings["name"])
                
                logger.info(f"КД обнаружено. {int(sleep_after_plant // 60)} мин" + (f" {int(sleep_after_plant % 60)} сек" if int(sleep_after_plant % 60) > 0 else "") + ", после посадки")
                await asyncio.sleep(sleep_after_plant)


                # --- БЛОК 3: ПОЛИВ ГРЯДОК ---
                lock_acquired = False
                sleep_after_water = random.uniform(1080, 1100)
                try:
                    if not await self.task_manager.acquire_lock(self.strings["name"]) or await self.task_manager.is_well_soon():
                        await asyncio.sleep(1)
                        continue
                    lock_acquired = True
                    await self.client.send_message(self.chat_id, "Муг")
                    await asyncio.sleep(random.uniform(3, 4))
                    get_mug2 = (await self.client.get_messages(self.chat_id, limit=1))[0]

                    for row in get_mug2.buttons:
                        for button in row:
                            if not re.match(button_text_2, button.button.text):
                                self.counter[button_text_2] += 1
                                continue
                            
                            await get_mug2.click(data=f'c_gryad {self.tg_id} g_open {self.counter[button_text_2]}'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2)) 
                            await get_mug2.click(data=f'c_gryad {self.tg_id} g_water {self.counter[button_text_2]}'.encode())
                            await self.client.send_message(notify_id, "💧 -1 водичка")
                            await asyncio.sleep(random.uniform(1.5, 2)) 
                            await get_mug2.click(data=f'c_gryad {self.tg_id} main'.encode())
                            await asyncio.sleep(random.uniform(1.5, 2)) 
                            self.counter[button_text_2] += 1
                            break
                        else: continue
                except Exception as e:
                    await self.client.send_message("me", f"🚫 Ошибка в поливе <b>'{button_text_2}'</b>\n<code>{e}</code>")
                finally:
                    if lock_acquired:
                        await self.task_manager.release_lock(self.strings["name"])
                logger.info(f"КД обнаружено. {int(sleep_after_water // 60)} мин" + (f" {int(sleep_after_water % 60)} сек" if int(sleep_after_water % 60) > 0 else "") + ", после поливания. Цикл завершен")
                await asyncio.sleep(sleep_after_water)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка: {e}", exc_info=True)
                await self.task_manager.release_lock(self.strings["name"])
                await asyncio.sleep(300)
        
        self.db.set(self.strings["name"], "enabled", False)
        logger.info("Loop stopped")

    async def get_status_text(self):
        enabled = self.db.get(self.strings["name"], "enabled", False)
        return f"{self.EMOJI} {self.strings['name']}: {'✅' if enabled else '❌'}"

    async def render_settings(self, call):
        item = self.db.get(self.strings["name"], "item", "не задано")
        text = f"<b>{self.EMOJI} Настройки грядок</b>\n\n<b>🌱 Сейчас растим:</b> <code>{item[:-2] if item.endswith(' &') else item}</code>"

        buttons = []
        row = [{'text': emoji, 'callback': self.item_selected, "args": (name,)} for emoji, name in self.all_items.items()]
        buttons.append(row)

        is_random = self.db.get(self.strings["name"], "random_schedule", False)
        random_btn_text = f"🕰️ Случайное время {'✅' if is_random else '❌'}"
        buttons.append([{'text': random_btn_text, 'callback': self.lookup("ControlPanelMod").toggle_random_schedule, "args": ("gryadka",)}])

        buttons.append([{'text': '⬅️ Назад', 'callback': self.lookup("ControlPanelMod").open_module_menu, "args": ("gryadka",)}])

        await call.edit(text, reply_markup=buttons)

    async def item_selected(self, call, item_name):
        self.db.set(self.strings["name"], "item", item_name)
        emoji = [k for k, v in self.all_items.items() if v == item_name][0]
        await call.answer(f"✅ Растение изменено на: {emoji}")
        await self.render_settings(call)