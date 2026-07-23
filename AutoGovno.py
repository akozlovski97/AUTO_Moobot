# AutoGovno.py
from .. import utils, loader
from telethon.errors.rpcerrorlist import MessageNotModifiedError 
import asyncio, random, re, logging

logger = logging.getLogger("GovnoMod")

@loader.tds
class GovnoMod(loader.Module): 
    """Автоматизация Говна""" 
    strings = {"name": "GovnoMod"}
    EMOJI = "💩"

    _EMOJI_DICT = {
        "ручка": "🖊️", "ёлка": "🎄", "молния": "⚡", "молитва": "🙏", "зонтик": "☔", "часы": "⌛", "корона": "👑", 
        "шарик": "🎈", "волна": "🌊", "флажок": "🚩", "радужка": "🌈", "вулкан": "🌋", "бомба": "💣", "солнце": "🌞", 
        "магнит": "🧲", "пицца": "🍕", "нло": "👽", "пиво": "🍺", "100-баллов": "💯", "пончик": "🍩", "туфля": "👠", 
        "смех": "😂", "телефон": "☎️", "автомобиль": "🚗", "джинсы": "👖", "булавка": "📌", "пшеничка": "🌾", 
        "папка": "📂", "звезда": "⭐️", "кактусик": "🌵", "велосипед": "🚲", "помада": "💄", "поезд": "🚂", 
        "рукопожатие": "🤝", "хлопушка": "🎉", "сон": "💤", "чёрная-луна": "🌚", "планета": "🌎", "футбол": "⚽️", 
        "персик": "🍑", "дизлайк": "👎", "компьютер": "🖥", "подсолнух": "🌻", "график": "📊", "хот-дог": "🌭", 
        "сок": "🧃", "лед": "🧊", "тигр": "🐯", "шарф": "🧣", "взрыв": "💥", "херомант": "👻", "футболка": "👕", 
        "вода": "💧", "блокнот": "📒", "сумка": "👜", "луна": "🌛", "фришка": "🍟", "книга": "📖", "дом": "🏠", 
        "кино": "🎬", "самолет": "✈️", "торт": "🎂", "огонь": "🔥", "леденец": "🍭", "коробок": "📦", "календарь": "📆", 
        "очки": "👓", "ракета": "🚀", "замок": "🏰", "картофель": "🥔", "ключ": "🔑", "обезьяна": "🐵", "цветик": "🌸", 
        "мороженое": "🍨", "масло": "🧈", "кепка": "🧢", "сэндвич": "🥪", "книги": "📚", "снежинка": "❄️", "микрофон": "🎤", 
        "корабль": "🚢", "джойстик": "🎮", "платье": "👗", "говно": "💩", "наушники": "🎧", "лампочка": "💡", "карандаш": "✏️", 
        "лайк": "👍", "рвота": "🤮", "таблетка": "💊", "лиса": "🦊", "тыква": "🎃", "бабочка": "🦋", "кольцо": "💍", 
        "кокос": "🥥", "палатка": "🏕", "лимон": "🍋", "ураган": "🌪", "пистолет": "🔫", "пятачок": "🐽", "кубок": "🏆", 
        "волк": "🐺", "перчатка": "🧤", "аплодисменты": "👏", "травка": "🌿", "кошелёк": "👛", "рюкзак": "🎒", "кроссовки": "👟", 
        "смартфон": "📱", "клевер": "🍀", "письмо": "✉️", "камера": "📷", "робот": "🤖", "коровка": "🐮", "листик": "🍁", 
        "дьявол": "😈", "пляж": "🏖", "яблоко": "🍎", "шляпа": "🎩", "статуя-свободы": "🗽", "розочка": "🌺", "кошка": "🐱", 
        "подарок": "🎁", "стадион": "🏟", "мясо": "🥩"}

    def __init__(self):
        self.tasks = []
        self.sok_message = None 
        self.govno_message = None

    async def client_ready(self, client, db): 
        self.db = db 
        self.client = client
        self.task_manager = self.lookup("TaskManagerMod")
        self.target_bot = 6396922937 
        
        self.db.set(self.strings["name"], "enabled", False)

        if self.db.get(self.strings["name"], "autostart", False):
            logger.info("⚡ Autostarting...")
            await self.start_task()

    async def start_task(self, call=None):
        if self.tasks: return
        await asyncio.sleep(4)
        self.db.set(self.strings["name"], "enabled", True)
        self.tasks.append(asyncio.create_task(self.sok_loop()))
        self.tasks.append(asyncio.create_task(self.govno_loop()))

    async def stop_task(self):
        self.db.set(self.strings["name"], "enabled", False)
        for task in self.tasks:
            if not task.done(): task.cancel()
        self.tasks.clear()

    def _replace_english_with_russian(self, text: str) -> str: 
        replacements = {'a': 'а', 'o': 'о', 'c': 'с', 'e': 'е', 'p': 'р', 'x': 'х', 'b': 'ь', 'y': 'у', "ë": "ё"} 
        def replace(match): 
            return replacements.get(match.group(0), match.group(0)) 
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+' 
        non_url_text = re.sub(url_pattern, '', text) 
        return re.sub(r'[a-zë]', replace, non_url_text).lower()

    async def sok_loop(self):
        logger.info("[SOK] Loop started")
        await asyncio.sleep(5) 
        while self.db.get(self.strings["name"], "enabled", False):
            if not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue

            lock_acquired = False
            error_occurred = False
            try:
                if not await self.task_manager.acquire_lock(self.strings["name"]):
                    await asyncio.sleep(1)
                    continue

                lock_acquired = True
                
                if not self.sok_message:
                    await self.client.send_message(self.target_bot, "Мз дерьмосок") 
                    await asyncio.sleep(4)
                    async for msg in self.client.iter_messages(self.target_bot, limit=10):
                        if msg.sender_id == self.target_bot and msg.buttons:
                            self.sok_message = msg
                            logger.info(f"[SOK] Session found: {msg.id}")
                            break
                    if not self.sok_message:
                        await self.task_manager.release_lock(self.strings["name"])
                        lock_acquired = False
                        await asyncio.sleep(60)
                        continue

                self.sok_message = await self.client.get_messages(self.target_bot, ids=self.sok_message.id)
                if not self.sok_message or not self.sok_message.buttons:
                    self.sok_message = None
                    continue

                data_payload = f'itmus {self.tg_id} дерьмосок'.encode('utf-8')
                await self.sok_message.click(data=data_payload)

            except asyncio.CancelledError: 
                break
            except Exception as e:
                logger.error(f"[SOK] Ошибка: {e}")
                self.sok_message = None
                error_occurred = True
            finally:
                if lock_acquired:
                    await self.task_manager.release_lock(self.strings["name"])
            
            if error_occurred:
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(random.uniform(68, 74))

        logger.info("[SOK] Loop stopped")

    async def govno_loop(self):
        logger.info("[MUK] Loop started")
        while self.db.get(self.strings["name"], "enabled", False):
            if not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue

            lock_acquired = False
            error_occurred = False
            try:
                notify_id = await self.lookup("ControlPanelMod").get_notify_id() 

                if not await self.task_manager.acquire_lock(self.strings["name"]):
                    await asyncio.sleep(1)
                    continue

                lock_acquired = True
                
                if not self.govno_message:
                    await self.client.send_message(self.target_bot, "Мук")
                    await asyncio.sleep(4)
                    async for msg in self.client.iter_messages(self.target_bot, limit=10):
                        if msg.sender_id == self.target_bot and msg.buttons:
                            self.govno_message = msg
                            logger.info(f"[MUK] Session found: {msg.id}")
                            break
                    if not self.govno_message:
                        await self.task_manager.release_lock(self.strings["name"])
                        lock_acquired = False
                        await asyncio.sleep(60)
                        continue

                self.govno_message = await self.client.get_messages(self.target_bot, ids=self.govno_message.id)
                if not self.govno_message or not self.govno_message.text:
                    self.govno_message = None
                    continue

                message_text_lower = self.govno_message.text.lower()

                if "💡 корово-капча" in message_text_lower:
                    replaced_text = self._replace_english_with_russian(message_text_lower)
                    captcha_solved = False
                    for word, emoji in self._EMOJI_DICT.items():
                        if word.lower() in replaced_text:
                            if self.govno_message.buttons:
                                for button_row in self.govno_message.buttons:
                                    for button in button_row:
                                        if emoji in button.text:
                                            await asyncio.sleep(random.uniform(2, 3))
                                            await button.click()
                                            await self.client.send_message(notify_id, f"💡 Корово-капча {button.text}")
                                            captcha_solved = True
                                            break
                                    if captcha_solved: break
                            if captcha_solved: break
                    if not captcha_solved:
                        await self.client.send_message("me", "<b>⚠️ Не удалось найти кнопку для решения капчи</b>")

                    await asyncio.sleep(random.uniform(2.5, 3.5))
                    updated_msg = await self.client.get_messages(self.target_bot, ids=self.govno_message.id)
                    
                    if updated_msg and updated_msg.text and "💡 корово-капча" in updated_msg.text.lower():
                        self.govno_message = None
                        await asyncio.sleep(300)
                    else:
                        self.govno_message = updated_msg
                    
                    continue

                if self.govno_message.buttons:
                    await self.govno_message.click(data=f'check_tools {self.tg_id}'.encode('utf-8'))
                    await asyncio.sleep(random.uniform(1.5, 3.5))
                    self.govno_message = await self.client.get_messages(self.target_bot, ids=self.govno_message.id)

                    await self.govno_message.click(data=f'profileback {self.tg_id}'.encode('utf-8'))
                    await asyncio.sleep(random.uniform(1.5, 3.5))
                    self.govno_message = await self.client.get_messages(self.target_bot, ids=self.govno_message.id)

                    clicked_final = False
                    for row in self.govno_message.buttons:
                        for button in row:
                            button_data = button.data.decode('utf-8')
                            if button_data.startswith('outshit') or button_data.startswith('milk'):
                                result = await button.click()
                                if hasattr(result, 'message') and result.message:
                                    await self.client.send_message(notify_id, result.message)
                                clicked_final = True
                                break
                        if clicked_final: break
            
            except MessageNotModifiedError:
                await asyncio.sleep(3)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MUK] Ошибка: {e}", exc_info=True)
                self.govno_message = None
                error_occurred = True
            finally:
                if lock_acquired:
                    await self.task_manager.release_lock(self.strings["name"])
            
            if error_occurred:
                await asyncio.sleep(300)
            else:
                interval = random.uniform(62, 90)
                await asyncio.sleep(interval)

        logger.info("[MUK] Loop stopped")

    async def render_settings(self, call):
        is_random = self.db.get(self.strings["name"], "random_schedule", False)
        random_btn_text = f"🕰️ Случайное время {'✅' if is_random else '❌'}"

        text = f"<b>{self.EMOJI} Настройки говна</b>"

        buttons = [
            [{'text': random_btn_text, 'callback': self.lookup("ControlPanelMod").toggle_random_schedule, "args": ("govno",)}],
            [{'text': '⬅️ Назад', 'callback': self.lookup("ControlPanelMod").open_module_menu, "args": ("govno",)}]]

        await call.edit(text, reply_markup=buttons)
    
    async def get_status_text(self):
        enabled = self.db.get(self.strings["name"], "enabled", False)
        return f"{self.EMOJI} {self.strings['name']}: {'✅' if enabled else '❌'}"