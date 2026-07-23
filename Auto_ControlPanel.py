# Auto_ControlPanel.py
from .. import loader, utils
from hikka.inline.types import InlineCall
import logging

logger = logging.getLogger("ControlPanel")

@loader.tds
class ControlPanelMod(loader.Module):
    """Центральная панель управления модулями"""
    strings = {"name": "ControlPanel"}

    async def client_ready(self, client, db):
        self.db = db
        self.client = client

        if self.db.get("ControlPanel", "notify_id", None) is None:
            me = await client.get_me()
            self.db.set("ControlPanel", "notify_id", me.id)

        self.module_map = {
            "well": "AutoWellMod",
            "gryadka": "GryadkaMod",
            "govno": "GovnoMod",
            "craft": "CraftMod",
            "muz": "MuzMod",
            "chick": "ChickMod",
            "fish": "FishMod"}

    async def get_module_instance(self, short_name):
        full_name = self.module_map.get(short_name)
        return self.lookup(full_name) if full_name else None

    @loader.command(alias="settings")
    async def autopcmd(self, event):
        """Панель управления ботами"""
        text = "<b>⚙️ Панель управления ботами</b>\n\n<i>Выберите модуль для управления:</i>"
        
        buttons = []
        for short_name in self.module_map:
            module = await self.get_module_instance(short_name)
            if module:
                status = "❓"
                if hasattr(module, 'get_status_text'):
                    status = await module.get_status_text()
                else:
                    name = module.strings.get("name", short_name)
                    enabled = module.db.get(name, "enabled", False)
                    status = f"{name}: {'✅' if enabled else '❌'}"
                
                buttons.append([{"text": f"{status}", "callback": self.open_module_menu, "args": (short_name,)}])
        
        buttons.append([{"text": "❌ Закрыть", "action": "close"}])

        if isinstance(event, InlineCall):
            await event.edit(text, reply_markup=buttons)
        else:
            await self.inline.form(text, message=event, reply_markup=buttons)

    async def open_module_menu(self, call, short_name):
        module = await self.get_module_instance(short_name)
        if not module: return await call.answer("⚠️ Модуль не найден (возможно, не загружен)!", show_alert=True)

        name = module.strings["name"]
        is_enabled = module.db.get(name, "enabled", False)
        autostart = module.db.get(name, "autostart", False)
        emoji = getattr(module, 'EMOJI', '⚙️')

        text = (
            f"<b>{emoji} Настройки «{name}»</b>\n\n"
            f"<b>Состояние:</b> {'✅ <code>Включен</code>' if is_enabled else '❌ <code>Отключен</code>'}\n"
            f"<b>Автозапуск:</b> {'✅ <code>Включен</code>' if autostart else '❌ <code>Отключен</code>'}")

        buttons = [
            [
                {"text": "🔴 Выключить" if is_enabled else "🟢 Включить", "callback": self.toggle_module, "args": (short_name,)},
                {"text": "Автозапуск ❌" if autostart else "Автозапуск ✅", "callback": self.toggle_autostart, "args": (short_name,)}]]
        
        if hasattr(module, 'render_settings'):
            buttons.append([{"text": "🛠 Настройки модуля", "callback": self.open_module_settings, "args": (short_name,)}])

        buttons.append([{"text": "⬅️ Назад", "callback": self.autopcmd}])

        await call.edit(text, reply_markup=buttons)

    async def toggle_module(self, call, short_name):
        module = await self.get_module_instance(short_name)
        if not module: return await call.answer("⚠️ Модуль не найден!", show_alert=True)

        name = module.strings["name"]
        is_enabled = module.db.get(name, "enabled", False)
        
        if is_enabled:
            if hasattr(module, 'stop_task'):
                await module.stop_task()
            else:
                module.db.set(name, "enabled", False)
            await call.answer("🔴 Модуль выключен")
        else:
            if hasattr(module, 'start_task'):
                result = await module.start_task(call)
                if result is not False:
                    await call.answer("🟢 Модуль включен")
            else:
                module.db.set(name, "enabled", True)
                await call.answer("🟢 Модуль включен")
            
        await self.open_module_menu(call, short_name)

    async def toggle_autostart(self, call, short_name):
        module = await self.get_module_instance(short_name)
        if not module: return await call.answer("⚠️ Модуль не найден!", show_alert=True)

        name = module.strings["name"]
        autostart = module.db.get(name, "autostart", False)
        module.db.set(name, "autostart", not autostart)
        
        await call.answer(f"{'✅' if not autostart else '❌'} Автозапуск {'выключен' if autostart else 'включен'}")
        await self.open_module_menu(call, short_name)
        
    async def open_module_settings(self, call, short_name):
        module = await self.get_module_instance(short_name)
        if not module: return await call.answer("⚠️ Модуль не найден!", show_alert=True)

        if hasattr(module, 'render_settings'):
            await module.render_settings(call)
        else:
            await call.answer("⚠️ У этого модуля нет настроек!", show_alert=True)

    async def toggle_random_schedule(self, call, short_name: str):
        module = await self.get_module_instance(short_name)
        if not module:
            return await call.answer("⚠️ Модуль не найден!", show_alert=True)

        module_name = module.strings["name"]
        is_random = module.db.get(module_name, "random_schedule", False)
        
        module.db.set(module_name, "random_schedule", not is_random)
        module.db.set(module_name, "schedule_date", None)

        await call.answer(f"{'✅' if not is_random else '❌'} Случайное время работы {'включено' if not is_random else 'выключено'}")

        if hasattr(module, 'render_settings'):
            await module.render_settings(call)
        else:
            await self.open_module_menu(call, short_name)

    async def get_notify_id(self):
        notify_id = self.db.get("ControlPanel", "notify_id", None)
        if notify_id is None:
            me = await self.client.get_me()
            notify_id = me.id
            self.db.set("ControlPanel", "notify_id", notify_id)
        return notify_id

    @loader.command(alias="setnotify")
    async def setnotifycmd(self, message):
        """ID чата для отправки уведомлений"""
        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        target_id = None
        if args and args.lstrip('-').isdigit():
            target_id = int(args)
        elif reply:
            target_id = reply.sender_id
        else:
            current_id = await self.get_notify_id()
            await utils.answer(
                message,
                f"<b>⚙️ Текущий ID для уведомлений:</b> <code>{current_id}</code>\n\n"
                f"Чтобы изменить, используйте <code>.setnotify (chat_id)</code> или ответьте на чьё-либо сообщение")
            return

        try:
            await self.client.get_entity(target_id)
            self.db.set("ControlPanel", "notify_id", target_id)
            await utils.answer(message, f"<b>✅ ID для уведомлений установлен на:</b> <code>{target_id}</code>")
        except Exception:
            await utils.answer(message, f"<b>🚫 Ошибка:</b> не удалось найти пользователя или чат с ID <code>{target_id}</code>")