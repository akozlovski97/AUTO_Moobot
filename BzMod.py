# BzMod.py
from .. import loader, utils
from telethon import events
import asyncio, re, random, logging

logger = logging.getLogger("BzMod")

@loader.tds
class BzModMod(loader.Module):
    """Автоматизация покупки на бз"""
    strings = {"name": "BzMod"}

    def __init__(self):
        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "min_delay",
                1.0,
                "Минимальная задержка (сек)",
                validator=loader.validators.Float()
            ),
            loader.ConfigValue(
                "max_delay",
                2.5,
                "Максимальная задержка (сек)",
                validator=loader.validators.Float()
            ),
        )
        self.running = False
        self.visited_buttons = set()
        self.monitor_msg_id = None
        self.chat_id = None

        self.target_emoji = None
        self.item_clicked_in_store = False

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.task_manager = self.lookup("TaskManagerMod")
        self.client.add_event_handler(
            self.on_message_edited,
            events.MessageEdited())

    async def _reset_state(self):
        self.visited_buttons = set()
        self.target_emoji = None
        self.item_clicked_in_store = False

    async def _stop_buying(self):
        if self.running:
            self.running = False
            await self._reset_state()
            if self.task_manager:
                await self.task_manager.release_lock(self.strings["name"])

    async def бзcmd(self, message):
        """Запуск скупки"""
        reply = await message.get_reply_message()
        if not reply:
            await utils.answer(message, "❌ Нужен реплай на сообщение с товарами")
            return

        prices = self.db.get("RinHelpMod", "prices", {})
        if not prices:
            await utils.answer(message, "⚠️ В базе нет цен (RinHelpMod)")

        while not await self.task_manager.acquire_lock(self.strings["name"]):
            await asyncio.sleep(1)

        self.chat_id = message.chat_id
        self.monitor_msg_id = reply.id
        self.running = True

        await self._reset_state()
        
        await message.delete()
        await self.process_message(reply)

    async def бзстопcmd(self, message):
        """Остановка и очистка кеша"""
        await self._stop_buying()
        await utils.answer(message, "🛑 Скупка остановлена, очередь освобождена")

    async def бзкешcmd(self, message):
        """Ручной сброс кеша"""
        await self._reset_state()
        await utils.answer(message, "🧹 Кеш сброшен")

    async def on_message_edited(self, event):
        if not self.running or event.chat_id != self.chat_id or event.id != self.monitor_msg_id:
            return

        delay = random.uniform(self.config['min_delay'], self.config['max_delay'])
        await asyncio.sleep(delay)
        await self.process_message(event.message)

    async def process_message(self, message):
        if not self.running:
            return

        text = message.text or ""
        rows = message.reply_markup.rows if message.reply_markup else []
        target_prices = self.db.get("RinHelpMod", "prices", {})

        if self.target_emoji:

            if "Мало муни" in text:
                logger.info(f"Не хватило муни чтобы купить {self.target_emoji}. Жму Назад")
                await self.click_button(message, ["назад", "back", "👈🏻"])
                return

            if "Товара же нету" in text:
                logger.info(f"Товара {self.target_emoji} нет в наличии (0). Жму Назад")
                await self.click_button(message, ["назад", "back", "👈🏻"])
                return

            if "Купил" in text and "шт" in text:
                qty = "?"
                price = "?"

                qty_match = re.search(r'Купил\s+(\d+)\s+шт', text)
                if qty_match:
                    qty = qty_match.group(1)

                price_match = re.search(r'за\s+([\d,]+)\s+муни', text)
                if price_match:
                    price = price_match.group(1)

                logger.info(f"Купил {self.target_emoji} {qty} шт. за {price} муни")

                await self.click_button(message, ["назад", "back", "👈🏻"])
                return

            if "для покупки" in text or "ответь" in text or ("|" in text and "владелец" not in text):
                try:
                    first_line = text.split('\n')[0].strip()
                    raw_stock = ""

                    if '|' in first_line:
                        parts = first_line.split('|')
                        if len(parts) > 1:
                            raw_stock = parts[-1].strip()

                    if not raw_stock:
                         raw_stock = first_line.split()[-1].strip()

                    clean_stock = re.sub(r'[^\d.,кk]', '', raw_stock.lower())

                    if clean_stock:
                        mult = 1
                        if 'к' in clean_stock or 'k' in clean_stock:
                            mult = 1000
                            clean_stock = clean_stock.replace('к', '').replace('k', '')

                        val = float(clean_stock.replace(',', '.')) * mult
                        real_stock = int(val)

                        digits = len(str(real_stock))
                        buy_amount = "9" * digits

                        await message.reply(buy_amount)
                        return
                    else:
                        logger.error(f"⚠️ Не смог извлечь цифры")

                except Exception as e:
                    logger.error(f"⚠️ Ошибка: {e}")

                await self.click_button(message, ["назад", "back", "👈🏻"])
                return

            if self.item_clicked_in_store:
                self.target_emoji = None
                self.item_clicked_in_store = False
                await self.click_button(message, ["назад", "back", "👈🏻"])
                return

            found_in_store = False
            for row in rows:
                for btn in row.buttons:
                    if self.target_emoji in btn.text:
                        self.item_clicked_in_store = True
                        await message.click(data=btn.data)
                        found_in_store = True
                        return

            if not found_in_store:
                self.target_emoji = None
                self.item_clicked_in_store = False
                await self.click_button(message, ["назад", "back", "👈🏻"])
                return

        for row in rows:
            for btn in row.buttons:
                if btn.data in self.visited_buttons:
                    continue

                btn_text = btn.text

                price_match = re.search(r'💰\s*([\d,]+)', btn_text)
                if not price_match:
                    continue

                total_price = int(price_match.group(1).replace(',', ''))

                count_match = re.search(r'(\d+)\s+по\s+💰', btn_text)
                count = int(count_match.group(1)) if count_match else 1

                unit_price = total_price // count

                item_emoji = None
                for emoji in target_prices.keys():
                    if emoji in btn_text:
                        item_emoji = emoji
                        break

                if not item_emoji:
                    continue

                max_price = target_prices[item_emoji]

                if unit_price <= max_price:
                    self.target_emoji = item_emoji
                    self.item_clicked_in_store = False
                    self.visited_buttons.add(btn.data)

                    await message.click(data=btn.data)
                    return

        await self.click_button(message, ["дальше", "next", "➡️", "вперед"], return_result=True)

    async def click_button(self, message, text_variants, return_result=False):
        if not message.reply_markup:
            return False

        for row in message.reply_markup.rows:
            for btn in row.buttons:
                if any(variant.lower() in btn.text.lower() for variant in text_variants):
                    try:
                        res = await message.click(data=btn.data)

                        if res and hasattr(res, 'message') and res.message:
                            msg_lower = res.message.lower()
                            if any(x in msg_lower for x in ["дальше ничё", "ничего", "пусто"]):
                                await self._stop_buying()
                                return False

                        return True
                    except Exception as e:
                        logger.error(f"⚠️ Ошибка клика: {e}")
                        return False
        return False