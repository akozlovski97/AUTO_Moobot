# RinHelpMod.py
from .. import loader, utils
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from telethon import events
import asyncio, re, logging

logger = logging.getLogger("RinHelpInteractive")

@loader.tds
class RinHelpInteractiveMod(loader.Module):
    """Интерактивный анализ рынка"""
    strings = {"name": "RinHelpInteractive"}

    def __init__(self):
        self.db = None
        self.normal_prices = {}
        self.pending_updates = {}

    async def client_ready(self, client, db):
        self.db = db
        self.client = client

        self.client.add_event_handler(
            self.on_message_edited,
            events.MessageEdited(incoming=True))

        self.normal_prices = self.db.get("RinHelpMod", "prices", {}) or {
            '🥛': 20, '💩': 29, '🥚': 30, '💧': 79, '🌰': 50, '🩸': 279, '🐟': 444,
            '🍄': 55, '🌿': 110, '🌾': 140, '🍅': 100, '🥕': 100, '🌽': 220, '🥬': 150, '🥔': 140, '🍓': 100, '🌸': 140, '🍊': 1000,
            '🧃': 89, '🍼': 100, '💊': 500, '🥦': 330, '🍵': 55, '🥤': 390, '🩹': 990, '🍗': 1100, 
            '🧈': 49, '🥠': 80, '🍚': 60, '🧀': 75, '🍪': 55, '🍦': 60, '🍨': 145, '🧇': 150, '🍳': 900, '🥨': 130, 
            '🍫': 150, '🥗': 1069, '🍩': 170, '🍰': 275, '🍯': 350, '🍕': 350, '🥮': 440, '🍟': 300, '🥣': 280,
            '🍔': 585, '🍿': 375, '🥫': 215, '🍺': 215, '🥪': 330, '🍞': 300, '🥧': 290, '🍣': 600, '🍲': 400, 
            '📦': 3000, '💈': 18000, '⚡️': 12500, '🍭': 175000, '🌀': 75000, '🐤': 30000, '💋': 265000, '💟': 215000, 
            '🐡': 15000, '👻': 250000, '🧚‍♀️': 150000, '🧦': 180000, '🛹': 50000, '🧲': 350000, '🧤': 25000, '🦋': 3000, '🔑': 6000,
            '🧬': 1500000, '🍾': 450000, '⭐️': 12000000, '🎲': 80000000, '🤖': 17500000, '🎖': 75000000, '🧛🏻‍♂️': 1500000,
            '📗': 69, '🍏': 69, '🦴': 69, '🎹': 69, '🔋': 69, '💉': 69, '📱': 69, '☘️': 69, '🪨': 69, '✨': 69, '🐚': 69, '🪵': 69, '🪓': 69, 
            '🔥': 69, '🪱': 69, '🐍': 69, '🧪': 69, '🎟': 100, '🧵': 1500, '🎣': 1000, '🗺': 2000, '🔫': 10000,
            '🎁': 385, '☔️': 390, '🧺': 900, '💍': 750, '✂️': 550, '🪣': 25000, '🐷': 23000, '🔦': 50000, '🥡': 14500, '🧩': 160, '🏀': 400, '🦄': 150000}

    async def on_message_edited(self, event):
        msg_id = event.id
        if msg_id in self.pending_updates:
            future = self.pending_updates[msg_id]
            if not future.done():
                future.set_result(event.message)

    async def рценыcmd(self, message):
        """Изменяет цены. Использование: .рцены 🥛 25, 💩 35"""
        args = message.raw_text.split(maxsplit=1)
        if len(args) < 2:
            await message.edit("⚠️ Укажите цены в формате: .рцены 🥛 25, 💩 35")
            return

        try:
            new_prices = {}
            pairs = args[1].split(", ")
            for pair in pairs:
                emoji, price = pair.split()
                new_prices[emoji] = int(price)

            self.normal_prices.update(new_prices)
            self.db.set("RinHelpMod", "prices", self.normal_prices)
            await message.edit("✅ Цены успешно обновлены!")
        except Exception as e:
            await message.edit(f"⚠️ Ошибка: {e}")

    async def рcmd(self, message):
        """Интерактивный анализ"""
        reply = await message.get_reply_message()
        if not reply:
            await message.edit("Нужно сделать реплай на сообщение с рынком")
            return

        chat_id = message.chat_id
        await message.delete()

        markup = await self.generate_markup(reply, chat_id)
        
        text_content = reply.text if reply.text else "Рынок"
        markup.append([{'text': '❌ Закрыть', 'action': 'close'}])

        await self.inline.form(message=message, text=text_content, reply_markup=markup)

    async def generate_markup(self, message_obj, chat_id):
        if not message_obj.reply_markup:
            return []

        pattern = r'(.*?)\s+(\d+)\s+(.*?)\s*💰\s*([\d,]+)'
        new_rows = []
        item_index = 1

        for row in message_obj.reply_markup.rows:
            new_row = []
            for button in row.buttons:
                original_text = button.text
                match = re.search(pattern, original_text)
                
                display_text = original_text
                
                if match:
                    emoji_name, num_str, name, price_str = match.groups()
                    emoji_name = emoji_name.strip()
                    name = name.strip()
                    count = int(num_str)
                    all_price = int(price_str.replace(',', '').replace(' ', '').strip())
                    unit_price = all_price // count
                    
                    normal_price = self.normal_prices.get(emoji_name, None)
                    if normal_price is not None:
                        status = "✅" if unit_price <= normal_price else "❌"
                    else:
                        status = "❓"

                    all_price_fmt = f"{all_price:,}".replace(",", ".")
                    unit_price_fmt = f"{unit_price:,}".replace(",", ".")

                    if count == 1:
                        display_text = f"{status} {item_index}. {emoji_name} {name}: {all_price_fmt}"
                    else:
                        display_text = f"{status} {item_index}. {emoji_name} {name}: {all_price_fmt} / {count} = {unit_price_fmt}"
                    
                    item_index += 1

                new_row.append({
                    'text': display_text,
                    'callback': self.create_callback(chat_id, message_obj.id, original_text)
                })
            new_rows.append(new_row)
        return new_rows

    def create_callback(self, chat_id, msg_id, btn_text):
        return lambda call: self.button_handler(call, chat_id, msg_id, btn_text)

    async def button_handler(self, call, chat_id, msg_id, btn_text):
        try:
            await call.answer("⏳")
        except:
            pass

        try:
            messages = await self.client.get_messages(chat_id, ids=[msg_id])
            if not messages:
                return
            original_msg = messages[0]

            future = asyncio.Future()
            self.pending_updates[msg_id] = future

            asyncio.create_task(original_msg.click(text=btn_text))
            
            updated_msg = None
            
            try:
                updated_msg = await asyncio.wait_for(future, timeout=4.0)
            except asyncio.TimeoutError:
                msgs = await self.client.get_messages(chat_id, ids=[msg_id])
                if msgs:
                    updated_msg = msgs[0]
            finally:
                self.pending_updates.pop(msg_id, None)

            if not updated_msg:
                return

            new_markup = await self.generate_markup(updated_msg, chat_id)
            new_markup.append([{'text': '❌ Закрыть', 'action': 'close'}])
            
            new_text = updated_msg.text if updated_msg.text else "Рынок"

            await call.edit(text=new_text, reply_markup=new_markup)

        except MessageNotModifiedError:
            pass
        except Exception as e:
            logger.error(f"⚠️ Ошибка: {e}")