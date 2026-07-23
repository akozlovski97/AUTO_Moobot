# AutoFish.py
from .. import loader, utils
from telethon import events
from collections import defaultdict
from datetime import datetime, timezone
import asyncio, random, re, logging

logger = logging.getLogger("FishMod")

@loader.tds
class FishMod(loader.Module):
    """Автоматизация Рыбалки"""
    strings = {"name": "FishMod"}
    EMOJI = "🎣"

    BTN_WATER = {'💧', '🍄', '☘️', '🧊'}
    BTN_SPECIAL_1 = '✨'
    BTN_SPECIAL_2 = '🧲'
    BTN_ANSWER = '💗 ответить'
    BTN_FINISH = '💫 закончить'
    IGNORED_ITEMS = {' ', '🌈', BTN_FINISH, BTN_ANSWER}

    def __init__(self):
        self.task = None
        self.bucket_task = None
        self.needs_equip = True
        self.needs_bucket_check = True
        self.bot_ids = [6467105350, 6770881933, 6396922937, 1606812809, 5641915741]
        self.target_bot = 6467105350
        self.tg_id = None
        self.pending_minigame = False
        self.game_msg_id = None
        self.needs_bucket_cleaning = False

    async def client_ready(self, client, db):
        self.client = client
        self.db = db
        self.task_manager = self.lookup("TaskManagerMod")
        
        me = await client.get_me()
        self.tg_id = me.id

        self.db.set(self.strings["name"], "enabled", False)

        if self.db.get(self.strings["name"], "spot", None) is None:
            self.db.set(self.strings["name"], "spot", "🏝 Причал")
        if self.db.get(self.strings["name"], "gear", None) is None:
            self.db.set(self.strings["name"], "gear", {"skate": True, "socks": False})
        if self.db.get(self.strings["name"], "food", None) is None:
            self.db.set(self.strings["name"], "food", {"🍵": True, "🌿": True, "🥤": False, "🥦": False, "🍗": False})
        if self.db.get(self.strings["name"], "bait", None) is None:
            self.db.set(self.strings["name"], "bait", {"🪱": True, "🦋": False})
        if self.db.get(self.strings["name"], "beer", None) is None:
            self.db.set(self.strings["name"], "beer", False)
        if self.db.get(self.strings["name"], "drop_small_fish", None) is None:
            self.db.set(self.strings["name"], "drop_small_fish", False)
        if self.db.get(self.strings["name"], "lvlup_priority", None) is None:
            self.db.set(self.strings["name"], "lvlup_priority", ["🪣 место", "🎣 броски", "😇 муд", "🧲 магнит", "👻 херомант", "😎 стонкс", "🕰 часики"])
        
        if self.db.get(self.strings["name"], "autostart", False):
            logger.info("⚡ Autostarting...")
            await self.start_task()

    async def start_task(self, call=None):
        if self.task and not self.task.done():
            return
            
        self.start_time = datetime.now(timezone.utc)
        self.game_msg_id = None
        self.ignored_msgs = set()
        self.pending_minigame = False
        
        self.db.set(self.strings["name"], "enabled", True)
        self.task = asyncio.create_task(self.fish_loop())
        self.bucket_task = asyncio.create_task(self.bucket_loop())

    async def stop_task(self):
        self.db.set(self.strings["name"], "enabled", False)
        self.game_msg_id = None
        self.pending_minigame = False
        if self.task and not self.task.done():
            self.task.cancel()
        if self.bucket_task and not self.bucket_task.done():
            self.bucket_task.cancel()

    # ================== ВОТЧЕР ПОЛОМОК ==================

    @loader.watcher(incoming=True)
    async def break_watcher(self, message):
        if not self.db.get(self.strings["name"], "enabled", False):
            return
        if getattr(message, "peer_id", None) and getattr(message.peer_id, "user_id", None) in self.bot_ids:
            text = message.text or ""
            if "У тебя сломался" in text and any(x in text for x in ["удочка", "карта", "носочки", "скейт"]):
                logger.info(f"[FISH] Обнаружена поломка предмета: {text}")
                self.needs_equip = True
                
                try:
                    notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                    item_mapping = {"удочка": "🎣", "карта": "🗺", "носочки": "🧦", "скейт": "🛹"}
                    
                    for item_name, emoji in item_mapping.items():
                        if item_name in text.lower():
                            await self.client.send_message(notify_id, f"{emoji} -1 {item_name}")
                            break
                except Exception as e:
                    logger.error(f"[FISH] Ошибка отправки уведомления о поломке: {e}")

    # ================== ВОТЧЕР АПА СКИЛЛОВ ==================

    @loader.watcher(incoming=True, edited=True)
    async def levelup_watcher(self, message):
        if not self.db.get(self.strings["name"], "enabled", False):
            return
        if getattr(message, "peer_id", None) and getattr(message.peer_id, "user_id", None) in self.bot_ids:
            text = message.text or ""
            if "Лвл-ап!" in text and "уровне" in text:
                if message.buttons:
                    for row in message.buttons:
                        for btn in row:
                            if "качнуть скилл" in btn.text.lower() or "🌈" in btn.text:
                                logger.info("[FISH] Обнаружен Лвл-ап, жму 'качнуть скилл'")
                                res = await self._click_and_wait(btn, message.id)
                                if res and not isinstance(res, str) and "Новый левел!" in (res.text or ""):
                                    await self._handle_skill_upgrade(res)
                                return
            elif "Новый левел!" in text and "выбери какой скилл" in text:
                await self._handle_skill_upgrade(message)

    async def _handle_skill_upgrade(self, msg):
        priorities = self.db.get(self.strings["name"], "lvlup_priority", [])
        if not msg.buttons:
            return
        
        available_skills = {}
        for row in msg.buttons:
            for btn in row:
                available_skills[btn.text.strip()] = btn
        
        for skill in priorities:
            for btn_text, btn in available_skills.items():
                if skill in btn_text or skill.split()[1] in btn_text:
                    logger.info(f"[FISH] Качаю скилл по приоритету: {btn_text}")
                    await self._click_and_wait(btn, msg.id)
                    try:
                        notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                        await self.client.send_message(notify_id, f"🆙 <b>Скилл:</b> {btn_text}")
                    except Exception:
                        pass
                    return
        logger.warning("[FISH] Не нашел подходящего скилла для прокачки!")

    # ================== УТИЛИТА КЛИКА ==================

    async def _click_and_wait(self, btn, msg_id, expected_data=None, timeout=6.0):
        """Продвинутый кликер, избегающий ошибки Encrypted data invalid"""
        await asyncio.sleep(random.uniform(1, 2.5))
        try:
            m_before = (await self.client.get_messages(self.target_bot, ids=[msg_id]))[0]
            if not m_before: return None
            old_text = m_before.text if m_before else ""
            
            if hasattr(btn, 'data') and btn.data:
                res = await m_before.click(data=btn.data)
            else:
                res = await btn.click()

            if res and hasattr(res, 'message') and res.message:
                logger.info(f"[FISH] Бот ответил: {res.message}")
                return "ALERT_" + res.message
        except Exception as e:
            logger.error(f"[FISH] Ошибка клика: {e}")
            return None
            
        for _ in range(int(timeout / 0.5)):
            await asyncio.sleep(0.5)
            m_after = (await self.client.get_messages(self.target_bot, ids=[msg_id]))[0]
            if not m_after: continue
            
            if expected_data:
                if m_after.buttons:
                    for row in m_after.buttons:
                        for b in row:
                            if b.data and expected_data in b.data:
                                return m_after
            elif m_after.text != old_text:
                return m_after
        
        return (await self.client.get_messages(self.target_bot, ids=[msg_id]))[0]

    # ================== НАВИГАЦИЯ ==================

    async def _navigate_to(self, msg, target_name):
        main_msg_id = msg.id
        target_keyword = target_name.lower().split()[-1][:4]
        
        for attempt in range(7):
            m_list = await self.client.get_messages(self.target_bot, ids=[main_msg_id])
            m = m_list[0] if m_list else None
            if not m or not m.text: return None
            
            text_lower = m.text.lower()

            if re.search(r'(\d+)\s*(мин|сек)', text_lower) or any(x in text_lower for x in ["направляемся", "идём", "идем"]):
                return m

            btn_target = None
            if m.buttons:
                for r in m.buttons:
                    for b in r:
                        if target_keyword in b.text.lower():
                            btn_target = b
                            break
                    if btn_target: break
            
            if btn_target:
                logger.info(f"[FISH] Навигация: жму '{btn_target.text}'")
                res = await self._click_and_wait(btn_target, main_msg_id)
                
                if isinstance(res, str) and any(x in res.lower() for x in ["голодн", "покорми", "кушать"]):
                    await self._feed_cow()
                    continue 
                
                if res and not isinstance(res, str): 
                    return res
                continue

            if "корово-окрестности" in text_lower:
                for r in m.buttons:
                    for b in r:
                        if "причал" in b.text.lower():
                            btn_target = b
                            break
                    if btn_target: break
                
                if btn_target:
                    logger.info(f"[FISH] Иду на Причал (промежуточная точка): жму '{btn_target.text}'")
                    res = await self._click_and_wait(btn_target, main_msg_id)
                    if isinstance(res, str) and any(x in res.lower() for x in ["голодн", "покорми", "кушать"]):
                        await self._feed_cow()
                        continue
                    if res and not isinstance(res, str):
                        return res
                    continue

            clicked_map = False
            
            if not any(x in text_lower for x in ["места", "окрестности"]):
                if m.buttons:
                    for r in m.buttons:
                        for b in r:
                            if "карта" in b.text.lower():
                                await self._click_and_wait(b, main_msg_id)
                                clicked_map = True
                                break
                        if clicked_map: break
            
            if clicked_map:
                await asyncio.sleep(2)
                continue

            if m.buttons:
                for r in m.buttons:
                    for b in r:
                        if "назад" in b.text.lower():
                            await self._click_and_wait(b, main_msg_id)
                            break
            
            await asyncio.sleep(1)
        return None

    # ================== ОСНОВНОЙ ЦИКЛ ==================

    async def fish_loop(self):
        logger.info("[FISH] Основной цикл запущен")
        while self.db.get(self.strings["name"], "enabled", False):
            if not await self.task_manager.check_schedule(self):
                await asyncio.sleep(60)
                continue

            lock_acquired = False
            sleep_duration = 30
            try:
                if not await self.task_manager.acquire_lock(self.strings["name"]):
                    await asyncio.sleep(2)
                    continue
                
                lock_acquired = True

                # 1. Если идет мини-игра
                if self.pending_minigame and self.game_msg_id:
                    msg_list = await self.client.get_messages(self.target_bot, ids=[self.game_msg_id])
                    msg = msg_list[0] if msg_list else None
                    if msg and msg.text and ("попыт" in msg.text.lower() or "рыбку" in msg.text.lower()):
                        sleep_duration = await self.perform_fishing_phase(msg.id)
                        raise ValueError("skip")
                    elif msg and msg.buttons and any(b.text in [self.BTN_SPECIAL_1, self.BTN_SPECIAL_2] for r in msg.buttons for b in r):
                        await self.perform_calculation_phase(msg.id)
                        self.pending_minigame = False
                        self.game_msg_id = None
                        sleep_duration = 5
                        raise ValueError("skip")
                    else: 
                        self.pending_minigame = False

                # 2. Фаза экипировки
                if self.needs_equip and not self.pending_minigame:
                    if not await self._equip_items():
                        sleep_duration = 30
                        raise ValueError("skip")
                    self.needs_equip = False
                    sleep_duration = 2
                    raise ValueError("skip")

                # 3. Стартовая проверка ведра
                if self.needs_bucket_check and not self.pending_minigame:
                    logger.info("[FISH] Стартовая проверка воды (Муф)...")
                    await self.client.send_message(self.target_bot, "Муф")
                    await asyncio.sleep(random.uniform(3, 5))
                    msg = await self._get_last_bot_msg()
                    if msg and msg.buttons:
                        for row in msg.buttons:
                            for btn in row:
                                if "ведро" in btn.text.lower():
                                    msg_bucket = await self._click_and_wait(btn, msg.id, expected_data=b'bins')
                                    if msg_bucket and not isinstance(msg_bucket, str):
                                        await self._refill_water(msg_bucket)
                                    break
                    self.needs_bucket_check = False
                    sleep_duration = 2
                    raise ValueError("skip")

                # 4. Поиск существующего меню (Расширен лимит и триггеры)
                msg = None
                if self.game_msg_id:
                    if hasattr(self, "ignored_msgs") and self.game_msg_id in self.ignored_msgs:
                        self.game_msg_id = None
                    else:
                        m_list = await self.client.get_messages(self.target_bot, ids=[self.game_msg_id])
                        msg = m_list[0] if m_list else None

                active_menu_triggers = ["муд", "места", "окрестности", "рыбку", "попыт", "ждём", "ждем", "направляемся", "идём", "идем", "лес", "клюёт"]

                if not msg or not msg.text or not any(x in msg.text.lower() for x in active_menu_triggers):
                    if not hasattr(self, "ignored_msgs"):
                        self.ignored_msgs = set()

                    async for m in self.client.iter_messages(self.target_bot, limit=10):
                        if hasattr(self, "start_time") and m.date < self.start_time:
                            continue

                        if (datetime.now(timezone.utc) - m.date).total_seconds() > 300:
                            continue
                            
                        if m.id in self.ignored_msgs:
                            continue

                        is_timer = m.text and any(x in m.text.lower() for x in ["ждём", "ждем", "направляемся", "идём", "идем", "отдохнуть", "приходи через"])
                        if not m.buttons and not is_timer:
                            self.ignored_msgs.add(m.id)
                            continue
                            
                        if m.text and any(x in m.text.lower() for x in active_menu_triggers):
                            msg = m
                            break

                use_existing = False
                if msg and msg.text:
                    t_low = msg.text.lower()
                    if any(x in t_low for x in active_menu_triggers):
                        use_existing = True
                        self.game_msg_id = msg.id
                        logger.info(f"[FISH] Использую найденное меню (ID: {msg.id})")

                # 5. Отправка Мулс (только если ничего не нашли)
                if not use_existing and not self.pending_minigame:
                    async with self.client.conversation(self.target_bot) as conv:
                        await conv.send_message("Мулс")
                        response = await conv.get_response()
                        self.game_msg_id = response.id
                        msg = response
                
                if not msg or not msg.text:
                    raise ValueError("skip")

                text_lower = msg.text.lower()
                
                # 6. Проверка КД и усталости
                cd_match = re.search(r'(\d+)\s*(мин|сек)', text_lower)
                if cd_match and any(x in text_lower for x in ["отдохнуть", "приходи через", "ждём", "ждем"]):

                    beer_enabled = self.db.get(self.strings["name"], "beer", False)
                    beer_btn = None
                    if beer_enabled and msg.buttons:
                        for row in msg.buttons:
                            for btn in row:
                                if "прибухнуть" in btn.text.lower() or "🍺" in btn.text:
                                    beer_btn = btn
                                    break
                            if beer_btn: break
                    
                    if beer_btn:
                        logger.info("[FISH] Пью пиво для сброса КД...")
                        res = await self._click_and_wait(beer_btn, msg.id)
                        target_chat_id = await self.lookup("ControlPanelMod").get_notify_id() 
                        await self.client.send_message(target_chat_id, "🍺 -1 пиво")

                        self.game_msg_id = msg.id
                        if hasattr(self, "ignored_msgs") and msg.id in self.ignored_msgs:
                            self.ignored_msgs.remove(msg.id)
                        
                        sleep_duration = 2
                        raise ValueError("skip")

                    val = int(cd_match.group(1))
                    is_mins = "мин" in cd_match.group(2)
                    wait_time = (val * 60 + 60) if is_mins else (val + 10)
                    sleep_duration = wait_time + random.uniform(2, 10)
                    m, s = divmod(int(sleep_duration), 60)
                    time_str = (f"{m} мин " if m else "") + (f"{s} сек" if s else "")
                    logger.info(f"[FISH] КД обнаружено. Сплю {time_str.strip()}")
                    
                    self.game_msg_id = None
                    if not hasattr(self, "ignored_msgs"): self.ignored_msgs = set()
                    self.ignored_msgs.add(msg.id)
                    raise ValueError("skip")
                
                # 7. Проверка пути
                if any(x in text_lower for x in ["направляемся", "идём", "идем"]):
                    path_match = re.search(r'(\d+)\s*(мин|сек)', text_lower)
                    if path_match:
                        val = int(path_match.group(1))
                        sleep_duration = (val * 60 + 60 if "мин" in path_match.group(2) else val + 10) + random.uniform(5, 15)
                    else:
                        sleep_duration = 60
                    
                    m, s = divmod(int(sleep_duration), 60)
                    time_str = (f"{m} мин " if m else "") + (f"{s} сек" if s else "")
                    logger.info(f"[FISH] В пути. Сплю {time_str.strip()}")

                    self.game_msg_id = None
                    if not hasattr(self, "ignored_msgs"): self.ignored_msgs = set()
                    self.ignored_msgs.add(msg.id)
                    raise ValueError("skip")

                # 8. Логика навигации или ловли
                if ("муд" in text_lower) or "места" in text_lower or "окрестности" in text_lower or "лес" in text_lower:
                    if getattr(self, "needs_bucket_cleaning", False) and self.db.get(self.strings["name"], "drop_small_fish", False):
                        msg = await self._clean_bucket_from_small_fish(msg) or msg
                        self.needs_bucket_cleaning = False
                    bucket_full = False
                    b_match = re.search(r'🪣\s*(\d+)/(\d+)', msg.text or "")

                    if not b_match:
                        for row in (msg.buttons or []):
                            for btn in row:
                                if "🪣" in getattr(btn, "text", ""):
                                    b_match = re.search(r'(\d+)/(\d+)', btn.text)
                                    if b_match: break
                            if b_match: break

                    if b_match:
                        curr_cap = int(b_match.group(1))
                        max_cap = int(b_match.group(2))
                        
                        if max_cap < 5:
                            bucket_full = (curr_cap == max_cap)
                        else:
                            bucket_full = (curr_cap >= max_cap - 1)

                    target = "🚢 порт" if bucket_full else self.db.get(self.strings["name"], "spot")
                    
                    target_key = target.split()[-1].lower()[:4]
                    if target_key not in text_lower or "места" in text_lower:
                        await self._navigate_to(msg, target)
                        sleep_duration = 2
                    else:
                        sleep_duration = await self._catch_fish(msg) or 5
                        if self.pending_minigame: raise ValueError("skip")

                elif "центр рыбаков" in text_lower or "рыбо-цех" in text_lower:
                    await self._port_and_slice(msg)
                    sleep_duration = 10
                elif "попыт" in text_lower or "рыбку" in text_lower:
                    self.game_msg_id = msg.id
                    sleep_duration = await self.perform_fishing_phase(msg.id)
                    raise ValueError("skip")
                elif "клюёт" in text_lower:
                    logger.info("[FISH] Найдена фаза калькуляции ('клюёт'), перехожу к подсчету.")
                    self.game_msg_id = msg.id
                    self.pending_minigame = True
                    await self.perform_calculation_phase(msg.id)
                    self.pending_minigame = False
                    self.game_msg_id = None
                    if not hasattr(self, "ignored_msgs"): self.ignored_msgs = set()
                    self.ignored_msgs.add(msg.id)
                    sleep_duration = 5
                    raise ValueError("skip")
                else:
                    sleep_duration = 15

            except asyncio.CancelledError: break
            except ValueError: pass
            except Exception as e:
                logger.error(f"[FISH] Ошибка основного цикла: {e}")
                sleep_duration = 60
            finally:
                if lock_acquired:
                    await self.task_manager.release_lock(self.strings["name"])
            
            if self.db.get(self.strings["name"], "enabled", False):
                await asyncio.sleep(sleep_duration)

    # ================== ФОНОВЫЕ ЗАДАЧИ ==================

    async def bucket_loop(self):
        while self.db.get(self.strings["name"], "enabled", False) and self.needs_bucket_check:
            await asyncio.sleep(2)

        if not self.db.get(self.strings["name"], "enabled", False):
            return

        await asyncio.sleep(1050 + random.uniform(5, 20))

        while self.db.get(self.strings["name"], "enabled", False):
            while self.db.get(self.strings["name"], "enabled", False):
                if not await self.task_manager.check_schedule(self):
                    await asyncio.sleep(60)
                    continue

                lock_acquired = False
                try:
                    if not await self.task_manager.acquire_lock(self.strings["name"]):
                        await asyncio.sleep(5)
                        continue
                    
                    lock_acquired = True
                    logger.info("[FISH] Фоновая проверка воды в ведре (Муф)...")
                    
                    await self.client.send_message(self.target_bot, "Муф")
                    await asyncio.sleep(random.uniform(3, 5))
                    msg = await self._get_last_bot_msg()

                    if msg and msg.buttons:
                        for row in msg.buttons:
                            for btn in row:
                                if "ведро" in btn.text.lower():
                                    msg_bucket = await self._click_and_wait(btn, msg.id, expected_data=b'bins')
                                    if msg_bucket and not isinstance(msg_bucket, str):
                                        await self._refill_water(msg_bucket)
                                    break
                    break 
                except Exception as e:
                    logger.error(f"[FISH] Ошибка в bucket_loop: {e}")
                    break
                finally:
                    if lock_acquired:
                        await self.task_manager.release_lock(self.strings["name"])

            if self.db.get(self.strings["name"], "enabled", False):
                await asyncio.sleep(1050 + random.uniform(5, 20))

    async def _get_last_bot_msg(self, limit=3):
        async for m in self.client.iter_messages(self.target_bot, limit=limit):
            if hasattr(self, "start_time") and m.date < self.start_time:
                continue
            if m.sender_id == self.target_bot:
                return m
        return None

    # ================== МИНИ-ИГРА И ЛОВЛЯ ==================

    def _get_click_data(self, action: str, value: int = "") -> bytes:
        return f'npc_inter {self.tg_id} fish {action} {value}'.strip().encode('utf-8')

    async def _catch_fish(self, msg):
        main_msg_id = msg.id
        bait_settings = self.db.get(self.strings["name"], "bait")

        bait_btn = None
        for row in (msg.buttons or []):
            for btn in row:
                if btn.data and b'fish bait' in btn.data:
                    bait_btn = btn
                    break
            if bait_btn: break

        if not bait_btn:
            return

        current_text = bait_btn.text

        used_bait_emoji = "🦋" if "🦋" in current_text else ("🪱" if "🪱" in current_text else None)

        only_butterflies = bait_settings.get("🦋") and not bait_settings.get("🪱")
        only_worms = bait_settings.get("🪱") and not bait_settings.get("🦋")
        both_baits = bait_settings.get("🦋") and bait_settings.get("🪱")
        
        need_menu = False
        if "✨" in current_text or " 0" in current_text:
            need_menu = True
        elif only_butterflies and "🦋" not in current_text:
            need_menu = True
        elif only_worms and "🪱" not in current_text:
            need_menu = True
        elif both_baits:
            need_menu = True

        if need_menu:
            logger.info("[FISH] Проверка/Смена наживки перед забросом...")
            msg = await self._click_and_wait(bait_btn, main_msg_id, expected_data = b'fish baitup')
            
            if msg and not isinstance(msg, str) and msg.buttons:
                bait_amounts = {"🪱": 0, "🦋": 0}
                bait_btns = {}

                for br in msg.buttons:
                    for bb in br:
                        if "🪱" in bb.text:
                            m = re.search(r'🪱\s*(\d+)', bb.text)
                            if m: bait_amounts["🪱"] = int(m.group(1))
                            bait_btns["🪱"] = bb
                        elif "🦋" in bb.text:
                            m = re.search(r'🦋\s*(\d+)', bb.text)
                            if m: bait_amounts["🦋"] = int(m.group(1))
                            bait_btns["🦋"] = bb

                target = None
                if bait_settings.get("🦋") and bait_amounts["🦋"] > 0:
                    target = "🦋"
                elif bait_settings.get("🪱") and bait_amounts["🪱"] > 0:
                    target = "🪱"
                
                if not target:
                    logger.warning("[FISH] Наживка закончилась! Останавливаю модуль")
                    await self.stop_task()
                    return

                if target in current_text and " 0" not in current_text:
                    logger.info(f"[FISH] {target} уже экипирована. Выхожу из меню.")
                    used_bait_emoji = target
                    for br in msg.buttons:
                        for bb in br:
                            if "назад" in bb.text.lower():
                                msg = await self._click_and_wait(bb, main_msg_id, expected_data = b'fish fly')
                                break
                else:
                    logger.info(f"[FISH] Надеваю {target} (доступно: {bait_amounts[target]})")
                    msg = await self._click_and_wait(bait_btns[target], main_msg_id, expected_data = b'fish fly')
                    used_bait_emoji = target
        
        # 3. После проверки наживки нажимаем 'ловим'
        if msg and not isinstance(msg, str) and msg.buttons:
            for row in msg.buttons:
                for btn in row:
                    if "ловим" in btn.text.lower():
                        res = await self._click_and_wait(btn, main_msg_id)

                        if used_bait_emoji:
                            try:
                                notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                                bait_name = "червь" if used_bait_emoji == "🪱" else "бабочка"
                                await self.client.send_message(notify_id, f"{used_bait_emoji} -1 {bait_name}")
                            except Exception as e:
                                logger.error(f"[FISH] Ошибка отправки уведомления о приманке: {e}")

                        if isinstance(res, str) and any(x in res.lower() for x in ["голодн", "покорми"]):
                            await self._feed_cow()
                            return

                        if res and not isinstance(res, str) and res.text:
                            if "попыт" in res.text.lower():
                                self.game_msg_id = res.id
                                self.pending_minigame = True
                                logger.info(f"[FISH] Удочка заброшена. ID игры: {res.id}")
                                return await self.perform_fishing_phase(res.id)
                        return
                    
    async def perform_fishing_phase(self, msg_id):
        self.pending_minigame = True
        
        bot_msg_list = await self.client.get_messages(self.target_bot, ids=[msg_id])
        if not bot_msg_list or not bot_msg_list[0].text: 
            return 15
            
        bot_msg = bot_msg_list[0]
        attempts_match = re.search(r'• (\d+) попыт', bot_msg.text)
        
        if not attempts_match:
            logger.info("[FISH][DEBUG] Не нашел количество попыток, выхожу")
            self.pending_minigame = False
            return 15

        attempts = int(attempts_match.group(1))
        logger.info(f"[FISH][DEBUG] Найдено попыток: {attempts}")
        
        if attempts == 0:
            logger.info("[FISH][DEBUG] Попыток 0, перехожу к подсчету")
            await self.perform_calculation_phase(msg_id)
            if not hasattr(self, "ignored_msgs"): self.ignored_msgs = set()
            self.ignored_msgs.add(msg_id)
            self.game_msg_id = None
            self.pending_minigame = False
            return 2

        for i in range(attempts):
            logger.info(f"[FISH][DEBUG] Итерация {i + 1} из {attempts}")
            if not self.db.get(self.strings["name"], "enabled", False): 
                break

            current_fish_msg = await self.client.get_messages(self.target_bot, ids=[msg_id])
            if not current_fish_msg or not current_fish_msg[0].buttons: 
                logger.info("[FISH][DEBUG] Нет кнопок, прерываю цикл")
                break
                
            msg = current_fish_msg[0]

            water_buttons = [b for row in msg.buttons for b in row if getattr(b, "text", "") in self.BTN_WATER]
            if not water_buttons: 
                logger.info("[FISH][DEBUG] Нет кнопок с водой, прерываю цикл")
                break

            target_btn = random.choice(water_buttons)
            
            try:
                logger.info("[FISH][DEBUG] Делаю двойной клик")
                if hasattr(target_btn, 'data') and target_btn.data:
                    await msg.click(data=target_btn.data)
                    await asyncio.sleep(random.uniform(0.8, 2.0))
                    await msg.click(data=target_btn.data)
                else:
                    await target_btn.click()
                    await asyncio.sleep(random.uniform(0.8, 2.0))
                    await target_btn.click()
            except Exception as e:
                logger.error(f"[FISH] Ошибка при клике: {e}")
                break

            await asyncio.sleep(random.uniform(1, 3))
            
            msg_with_timer = await self.client.get_messages(self.target_bot, ids=[msg_id])
            if not msg_with_timer or not msg_with_timer[0].text: 
                continue

            wait_time_match = re.search(r'ждём (\d+) мин', msg_with_timer[0].text)
            if wait_time_match:
                minutes = int(wait_time_match.group(1))
                wait_seconds = (minutes * 60) + 60 + random.uniform(2, 5)
                m, s = divmod(int(wait_seconds), 60)
                time_str = (f"{m} мин " if m else "") + (f"{s} сек" if s else "")
                logger.info(f"[FISH] КД обнаружено. {time_str.strip()}")
                
                await self.task_manager.release_lock(self.strings["name"])
                await asyncio.sleep(wait_seconds)
                while not await self.task_manager.acquire_lock(self.strings["name"]):
                    await asyncio.sleep(2)
            else:
                logger.info("[FISH][DEBUG] Таймера нет, небольшая пауза")
                await asyncio.sleep(random.uniform(1, 3))

        logger.info("[FISH][DEBUG] Цикл завершен, перехожу к подсчету")
        await self.client.send_message(self.target_bot, "Мулс")
        await asyncio.sleep(3)
        await self.perform_calculation_phase(msg_id)
        if not hasattr(self, "ignored_msgs"): self.ignored_msgs = set()
        self.ignored_msgs.add(msg_id)
        self.game_msg_id = None
        self.pending_minigame = False
        return 5

    async def perform_calculation_phase(self, msg_id):
        while self.db.get(self.strings["name"], "enabled", False):
            msg = await self._get_last_bot_msg()
            if not msg or not msg.buttons: break

            is_calculation_screen = any(self.BTN_ANSWER in b.text for r in msg.buttons for b in r)
            
            if is_calculation_screen:
                await self._process_calculation_round(msg)
            else:
                special_buttons = [b for r in msg.buttons for b in r if b.text in [self.BTN_SPECIAL_1, self.BTN_SPECIAL_2]]
                
                if not special_buttons:
                    try:
                        await msg.click(data=self._get_click_data("end"))
                        await asyncio.sleep(random.uniform(1.5, 2.5))
                    except Exception: pass
                    break
                
                if hasattr(special_buttons[0], 'data') and special_buttons[0].data:
                    await msg.click(data=random.choice(special_buttons).data)
                else:
                    await random.choice(special_buttons).click()
                await asyncio.sleep(random.uniform(2, 3))

    async def _process_calculation_round(self, round_msg):
        msg_id = round_msg.id
        
        # === БЫСТРЫЙ ВЫХОД ЕСЛИ ВРЕМЯ ВЫШЛО ===
        if "у тебя 0" in (round_msg.text or "").lower():
            logger.warning("[FISH] Время на подсчет вышло ('у тебя 0'). Выбираю наугад для сброса зависания!")
            
            fresh_msg = round_msg
            has_answer = any(self.BTN_ANSWER in getattr(b, "text", "") for r in fresh_msg.buttons for b in r)
            
            # Шаг 1: Жмем "ответить" (если кнопка еще есть)
            if has_answer:
                await asyncio.sleep(random.uniform(0.8, 2))
                try:
                    for row in fresh_msg.buttons:
                        for btn in row:
                            if self.BTN_ANSWER in getattr(btn, "text", ""):
                                if hasattr(btn, 'data') and btn.data:
                                    await fresh_msg.click(data=btn.data)
                                else:
                                    await btn.click()
                                break
                except Exception as e:
                    logger.error(f"[FISH] Ошибка клика 'ответить': {e}")
                
                await asyncio.sleep(random.uniform(1.5, 2.5))
                msgs = await self.client.get_messages(self.target_bot, ids=[msg_id])
                fresh_msg = msgs[0] if msgs else fresh_msg

            # Шаг 2: Жмем любую случайную цифру
            has_digits = any(getattr(b, "text", "").strip().isdigit() for r in fresh_msg.buttons for b in r)
            if has_digits:
                all_numbers = [b for r in fresh_msg.buttons for b in r if getattr(b, "text", "").strip().isdigit()]
                if all_numbers:
                    rand_btn = random.choice(all_numbers)
                    try:
                        if hasattr(rand_btn, 'data') and rand_btn.data:
                            await fresh_msg.click(data=rand_btn.data)
                        else:
                            await rand_btn.click()
                    except Exception as e:
                        logger.error(f"[FISH] Ошибка клика по случайной цифре: {e}")
                
                await asyncio.sleep(random.uniform(1.5, 2.5))
                msgs = await self.client.get_messages(self.target_bot, ids=[msg_id])
                fresh_msg = msgs[0] if msgs else fresh_msg

            # Шаг 3: Выходим из меню (Жмем кнопку с fish back)
            if fresh_msg.buttons:
                for row in fresh_msg.buttons:
                    for btn in row:
                        if getattr(btn, 'data') and b'fish back' in btn.data:
                            try:
                                if hasattr(btn, 'data') and btn.data:
                                    await fresh_msg.click(data=btn.data)
                                else:
                                    await btn.click()
                            except: pass
                            return None
            return None
        
        button_counts = defaultdict(int)
        
        # 1. Считаем предметы на экране
        for row in round_msg.buttons:
            for button in row:
                text = getattr(button, "text", "")
                clean_text = text.strip()
                if clean_text and clean_text not in self.IGNORED_ITEMS and clean_text != '🌈':
                    button_counts[clean_text] += 1
        
        if not button_counts: 
            return None

        logger.info(f"[FISH][DEBUG] Элементы для подсчета: {dict(button_counts)}")

        multipliers = {}
        msg_id = round_msg.id
        
        # 2. Узнаем вес каждого предмета
        for emoji in button_counts.keys():
            if not self.db.get(self.strings["name"], "enabled", False): 
                return None
                
            fresh_msg_list = await self.client.get_messages(self.target_bot, ids=[msg_id])
            if not fresh_msg_list or not fresh_msg_list[0].buttons: 
                continue
            fresh_msg = fresh_msg_list[0]
            
            target_btn = None
            for row in fresh_msg.buttons:
                for btn in row:
                    if getattr(btn, "text", "").strip() == emoji:
                        target_btn = btn
                        break
                if target_btn: break
            
            if not target_btn: 
                continue
            
            try:
                logger.info(f"[FISH][DEBUG] Кликаю на {emoji} для получения числа")
                if hasattr(target_btn, 'data') and target_btn.data:
                    res = await fresh_msg.click(data=target_btn.data)
                else:
                    res = await target_btn.click()
                    
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                if res and hasattr(res, 'message') and res.message:
                    value_match = re.search(r'=\s*(\d+)', res.message)
                    if value_match:
                        multipliers[emoji] = int(value_match.group(1))
                        logger.info(f"[FISH][DEBUG] Найдено: {emoji} = {multipliers[emoji]}")
                    else:
                        logger.warning(f"[FISH][DEBUG] Не смог найти число в алерте: {res.message}")
            except Exception as e:
                logger.error(f"[FISH] Ошибка получения веса для {emoji}: {e}")
                continue
        
        # 3. Считаем итоговую сумму
        total_sum = sum(multipliers.get(emoji, 0) * count for emoji, count in button_counts.items())
        logger.info(f"[FISH][DEBUG] Итоговая сумма для ответа: {total_sum}")

        # 4. Нажимаем кнопку "ответить"
        fresh_msg_list = await self.client.get_messages(self.target_bot, ids=[msg_id])
        if fresh_msg_list and fresh_msg_list[0].buttons:
            fresh_msg = fresh_msg_list[0]
            try:
                answer_btn = None
                for row in fresh_msg.buttons:
                    for btn in row:
                        if self.BTN_ANSWER in getattr(btn, "text", ""):
                            answer_btn = btn
                            break
                    if answer_btn: break
                
                if answer_btn:
                    if hasattr(answer_btn, 'data') and answer_btn.data:
                        await fresh_msg.click(data=answer_btn.data)
                    else:
                        await answer_btn.click()
                else:
                    await fresh_msg.click(data=self._get_click_data("prepull"))
            except Exception as e:
                logger.error(f"[FISH] Ошибка при нажатии 'ответить': {e}")
                
            await asyncio.sleep(random.uniform(1.5, 2.5))
        
        # 5. Ищем обновленное сообщение с вариантами цифр
        target_num_btn = None
        msg_with_answers = None
        
        for _ in range(5): 
            fresh_msg_list = await self.client.get_messages(self.target_bot, ids=[msg_id])
            if fresh_msg_list and fresh_msg_list[0].buttons:
                msg_with_answers = fresh_msg_list[0]
                for row in msg_with_answers.buttons:
                    for btn in row:
                        if str(total_sum) == getattr(btn, "text", "").strip():
                            target_num_btn = btn
                            break
                    if target_num_btn: break
            
            if target_num_btn:
                break
            await asyncio.sleep(1)

        # 6. Нажимаем правильную цифру (или случайную при ошибке)
        if target_num_btn and msg_with_answers:
            try:
                logger.info(f"[FISH][DEBUG] Нажимаю на правильный ответ: {total_sum}")
                if hasattr(target_num_btn, 'data') and target_num_btn.data:
                    await msg_with_answers.click(data=target_num_btn.data)
                else:
                    await target_num_btn.click()
            except Exception as e:
                logger.error(f"[FISH] Ошибка при нажатии цифры {total_sum}: {e}")
        else:
            logger.error(f"[FISH] Не смог найти кнопку с ответом {total_sum} на экране!")
            if msg_with_answers and msg_with_answers.buttons:
                all_numbers = [b for r in msg_with_answers.buttons for b in r if getattr(b, "text", "").strip().isdigit()]
                if all_numbers:
                    rand_btn = random.choice(all_numbers)
                    logger.warning(f"[FISH][DEBUG] Жму наугад: {rand_btn.text}, чтобы не застрять!")
                    try:
                        if hasattr(rand_btn, 'data') and rand_btn.data:
                            await msg_with_answers.click(data=rand_btn.data)
                        else:
                            await rand_btn.click()
                    except Exception:
                        pass
            
        await asyncio.sleep(random.uniform(1.5, 2.5))
        
        # 7. Читаем результат (улов) и возвращаемся
        final_msg_list = await self.client.get_messages(self.target_bot, ids=[msg_id])
        if final_msg_list:
            final_msg = final_msg_list[0]
            
            if getattr(final_msg, "text", None):
                await self._parse_and_log_catch(final_msg.text)

            # 8. Нажимаем назад/закончить
            try:
                back_btn = None
                if final_msg.buttons:
                    for row in final_msg.buttons:
                        for btn in row:
                            if getattr(btn, 'data') and b'fish back' in btn.data:
                                back_btn = btn
                                break
                        if back_btn: break
                
                if back_btn:
                    if hasattr(back_btn, 'data') and back_btn.data:
                        await final_msg.click(data=back_btn.data)
                    else:
                        await back_btn.click()
                else:
                    await final_msg.click(data=self._get_click_data("back"))
            except Exception: 
                pass
            
            await asyncio.sleep(random.uniform(1.5, 2.5))
        
        return None

    async def _parse_and_log_catch(self, message_text: str):
        try:
            target_chat_id = await self.lookup("ControlPanelMod").get_notify_id() 
            output_message = ""

            if '<code>вес</code>' in message_text:
                lines = message_text.split('\n')
                fish_name_line = lines[0]
                weight_match = re.search(r"<code>вес</code>\s*<b>(.*?)</b>", message_text)
                if weight_match:
                    weight = weight_match.group(1).lower()
                    output_message = f'{fish_name_line}, {weight}'

                    if self.db.get(self.strings["name"], "drop_small_fish", False):
                        if " г" in weight and "кг" not in weight:
                            self.needs_bucket_cleaning = True
                            logger.info(f"[FISH] Поймана мелкая рыба ({weight}), запланирована очистка ведра.")

            elif 'Ты выловил\nсокровище' in message_text:
                items = re.findall(r"<b>(\d+)</b>\s*(.+?)\s*<i>", message_text)
                if items:
                    formatted_items = [f"+{amount} {emoji.strip()}" for amount, emoji in items]
                    output_message = f"<b>🧲 сокровище</b>, {', '.join(formatted_items)}"

            if output_message:
                await self.client.send_message(target_chat_id, output_message, parse_mode="html")

        except Exception as e:
            logger.error(f"[FISH] Ошибка при анализе улова: {e}")

    # ================== ЛОГИКА НАВИГАЦИИ И ЭКИПИРОВКИ ==================

    async def _equip_items(self):
        logger.info("[FISH] Проверка и надевание экипировки")
        await asyncio.sleep(2)
        gear = self.db.get(self.strings["name"], "gear")
        
        target_mapping = {"🎣": "удочка", "🗺": "карта"}
        if gear.get("skate"): target_mapping["🛹"] = "скейт"
        if gear.get("socks"): target_mapping["🧦"] = "носочки"

        ignored_missing = set()

        await self.client.send_message(self.target_bot, "Муп")
        await asyncio.sleep(random.uniform(2, 4))
        main_msg = await self._get_last_bot_msg()
        
        if not main_msg or not main_msg.buttons: return False
        main_msg_id = main_msg.id

        for _ in range(15): 
            msg_list = await self.client.get_messages(self.target_bot, ids=[main_msg_id])
            if not msg_list or not msg_list[0] or not msg_list[0].buttons: return False
            msg = msg_list[0]

            equipped_emojis = set()
            free_slots = []
            junk_slots = []

            for row in msg.buttons:
                for btn in row:
                    text = btn.text
                    if "назад" in text.lower(): continue
                    
                    if btn.data and b'thingswear' in btn.data:
                        if "🤚🏻" in text or "пусто" in text.lower():
                            free_slots.append(btn)
                        else:
                            found_target = None
                            for te in target_mapping.keys():
                                if te in text:
                                    found_target = te
                                    break
                            
                            if found_target:
                                equipped_emojis.add(found_target)
                            else:
                                junk_slots.append(btn)

            missing_emojis = (set(target_mapping.keys()) - equipped_emojis) - ignored_missing

            if not missing_emojis:
                logger.info("[FISH] Все необходимые предметы успешно экипированы")
                return True

            target_emoji = list(missing_emojis)[0]
            logger.info(f"[FISH] Нужно надеть: {target_mapping[target_emoji]} ({target_emoji})")

            slot_to_click = free_slots[0] if free_slots else (junk_slots[0] if junk_slots else None)
            is_junk = not bool(free_slots)
            
            if not slot_to_click:
                logger.warning("[FISH] Нет свободных слотов для всей выбранной экипировки")
                return True

            cat_msg = await self._click_and_wait(slot_to_click, main_msg_id, expected_data=b'thingo')
            
            if isinstance(cat_msg, str) and "ALERT_" in cat_msg:
                logger.info("[FISH] Корова гуляет, нельзя менять вещи")
                return False

            success_equip = False
            if cat_msg and not isinstance(cat_msg, str) and cat_msg.buttons:
                clicked_cat = False
                for row in cat_msg.buttons:
                    for btn in row:
                        if target_emoji in btn.text and btn.data and b'thingo' in btn.data:
                            dur_msg = await self._click_and_wait(btn, main_msg_id, expected_data=b'thingsselect')
                            clicked_cat = True
                            
                            if dur_msg and not isinstance(dur_msg, str) and dur_msg.buttons:
                                available_items = [dbtn for drow in dur_msg.buttons for dbtn in drow if target_emoji in dbtn.text and dbtn.data and b'thingsselect' in dbtn.data]
                                if available_items:
                                    chosen_item = random.choice(available_items)
                                    final_msg = await self._click_and_wait(chosen_item, main_msg_id, expected_data=b'thingswear')
                                    if final_msg and not isinstance(final_msg, str):
                                        success_equip = True
                                        logger.info(f"[FISH] Успешно надел: {target_mapping[target_emoji]} ({target_emoji})")
                            break
                    if clicked_cat: break

            if not success_equip:
                logger.warning(f"[FISH] {target_mapping[target_emoji]} не удалось надеть напрямую")
                ignored_missing.add(target_emoji)
                curr_msg_list = await self.client.get_messages(self.target_bot, ids=[main_msg_id])
                if curr_msg_list and curr_msg_list[0] and curr_msg_list[0].buttons:
                    current_buttons = [btn for row in curr_msg_list[0].buttons for btn in row]
                    
                    if is_junk:
                        un_equipped = False
                        for btn in current_buttons:
                            if "снять" in btn.text.lower() or "🙅" in btn.text:
                                await self._click_and_wait(btn, main_msg_id, expected_data=b'thingswear')
                                un_equipped = True
                                break
                        if not un_equipped:
                            for btn in current_buttons:
                                if "назад" in btn.text.lower():
                                    await self._click_and_wait(btn, main_msg_id, expected_data=b'thingswear')
                                    break
                    else:
                        for btn in current_buttons:
                            if "назад" in btn.text.lower():
                                await self._click_and_wait(btn, main_msg_id, expected_data=b'thingswear')
                                break

        return False

    async def _feed_cow(self):
        logger.info("[FISH] Кормлю коровку (Мз)...")
        food_settings = self.db.get(self.strings["name"], "food")
        allowed_foods = [emoji for emoji, enabled in food_settings.items() if enabled]

        await self.client.send_message(self.target_bot, "Мз")
        await asyncio.sleep(random.uniform(3, 5))
        msg = await self._get_last_bot_msg()

        if msg and msg.buttons:
            for food_emoji in allowed_foods:
                for row in msg.buttons:
                    for btn in row:
                        if food_emoji in btn.text:
                            logger.info(f"[FISH] Коровка кушает {food_emoji}")
                            await btn.click()
                            await asyncio.sleep(random.uniform(2, 4))
                            return
        logger.warning("[FISH] Не удалось покормить коровку (нет еды или кнопок)")

    async def _port_and_slice(self, msg):
        mid = msg.id

        if "рыбо-цех" not in msg.text.lower():
            for row in (msg.buttons or []):
                for btn in row:
                    if "рыбо-цех" in btn.text.lower():
                        msg = await self._click_and_wait(btn, mid, expected_data=b'port slice_slct')
                        break
        
        if not msg or isinstance(msg, str): return

        # 1. Логика сбора готовой рыбы
        if "готовы" in msg.text:
            logger.info("[FISH][SLICE] Найдена кнопка 'забрать' (рыба готова)")
            for row in (msg.buttons or []):
                for btn in row:
                    if "забрать" in btn.text.lower():
                        logger.info("[FISH][SLICE] Кликаю 'забрать'")
                        await self._click_and_wait(btn, mid, expected_data=b'port opn_slice')
                        logger.info("[FISH][SLICE] Жду 2 секунды появления нового сообщения...")
                        await asyncio.sleep(2)
                        
                        # Ищем отдельное сообщение "нарезал рыбку" в последних 3 сообщениях
                        found_cut_msg = False
                        async for new_msg in self.client.iter_messages(self.target_bot, limit=3):
                            if new_msg.text:
                                logger.info(f"[FISH][SLICE] Проверяю сообщение: {new_msg.text[:50].replace(chr(10), ' ')}...")
                                if "нарезал рыбку" in new_msg.text.lower():
                                    found_cut_msg = True
                                    logger.info("[FISH][SLICE] Найдено сообщение о нарезке! Ищу регуляркой \\+\\s*(\\d+)\\s*🐟")
                                    match = re.search(r'\+\s*(\d+)\s*🐟', new_msg.text)
                                    if match:
                                        logger.info(f"[FISH][SLICE] Успех! Найдено число: {match.group(1)}")
                                        try:
                                            notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                                            await self.client.send_message(notify_id, f"🐟 +{match.group(1)} рыба")
                                        except Exception as e:
                                            logger.error(f"[FISH] Ошибка уведомления о сборе: {e}")
                                    else:
                                        logger.warning(f"[FISH][SLICE] Регулярка НЕ НАШЛА совпадений в тексте: {new_msg.text}")
                                    break
                        if not found_cut_msg:
                            logger.warning("[FISH][SLICE] Сообщение со словами 'нарезал рыбку' не найдено в последних 3-х сообщениях")
                            
                        # Обновляем главное сообщение с меню
                        msg_list = await self.client.get_messages(self.target_bot, ids=[mid])
                        if msg_list: 
                            msg = msg_list[0]
                            
                        # Возвращаемся в главное меню цеха
                        back_clicked = False
                        for r in (msg.buttons or []):
                            for b in r:
                                if "назад" in b.text.lower() or "👈🏻" in b.text:
                                    logger.info("[FISH][SLICE] Жму 'назад' после сбора")
                                    msg = await self._click_and_wait(b, mid)
                                    back_clicked = True
                                    break
                            if back_clicked: break
                        break

        # 2. Запоминаем изначальное количество рыбы в процессе
        initial_slicing = 0
        if msg and not isinstance(msg, str) and msg.text:
            logger.info(f"[FISH][SLICE] Ищу начальное кол-во рыбы в тексте: {msg.text.replace(chr(10), ' ')}")
            match = re.search(r'🐟\s*(\d+)', msg.text)
            if match:
                initial_slicing = int(match.group(1))
                logger.info(f"[FISH][SLICE] Найдено начальное кол-во: {initial_slicing}")
            else:
                logger.warning("[FISH][SLICE] Не удалось найти начальное кол-во (регулярка не сработала)")

        while True:
            btn_to_list = None
            if msg and not isinstance(msg, str) and msg.buttons:
                for r in msg.buttons:
                    for b in r:
                        if any(x in b.text.lower() for x in ["выбрать", "закинуть ещё"]):
                            btn_to_list = b; break
                    if btn_to_list: break
            
            if not btn_to_list: break

            msg = await self._click_and_wait(btn_to_list, mid, expected_data=b'port s-slct')
            if not msg or isinstance(msg, str) or not msg.buttons: break

            btn_target = None
            for r in msg.buttons:
                for b in r:
                    if b.data and b'port s-slct' in b.data:
                        btn_target = b; break
                if btn_target: break
            
            if btn_target:
                item_text = btn_target.text
                res = await self._click_and_wait(btn_target, mid, expected_data=b'port slice_slct')

                if isinstance(res, str) and "протухла" in res:
                    logger.info(f"[FISH] Обьект протух: {item_text}. Выкидываю через Муф")
                    await self._drop_rotten_fish()
                    return 
                
                msg = res
                if not msg: break
            else:
                for r in msg.buttons:
                    for b in r:
                        if "назад" in b.text.lower():
                            msg = await self._click_and_wait(b, mid)
                            break
                break

        # 3. Считаем разницу и отправляем уведомление о добавлении
        if msg and not isinstance(msg, str) and msg.text:
            final_slicing = 0
            logger.info(f"[FISH][SLICE] Ищу финальное кол-во рыбы в тексте: {msg.text.replace(chr(10), ' ')}")
            match = re.search(r'🐟\s*(\d+)', msg.text)
            if match:
                final_slicing = int(match.group(1))
                logger.info(f"[FISH][SLICE] Найдено финальное кол-во: {final_slicing}")
            else:
                logger.warning("[FISH][SLICE] Не удалось найти финальное кол-во (регулярка не сработала)")
                
            sliced_amount = final_slicing - initial_slicing
            logger.info(f"[FISH][SLICE] Разница: {final_slicing} - {initial_slicing} = {sliced_amount}")
            
            if sliced_amount > 0:
                try:
                    notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                    await self.client.send_message(notify_id, f"🐟 +{sliced_amount} рыба (⌛️ {final_slicing})")
                    logger.info("[FISH][SLICE] Уведомление о закидывании успешно отправлено")
                except Exception as e:
                    logger.error(f"[FISH] Ошибка уведомления о нарезке: {e}")

        logger.info("[FISH] Нарезку закончили, возращаюсь на причал")
        await self._navigate_to(msg, "🏖 причал")

    async def _clean_bucket_from_small_fish(self, main_msg):
        logger.info("[FISH] Проверяю ведро на наличие мелкой рыбы (< 1 кг)...")
        mid = main_msg.id
        
        # Определяем, заполнено ли ведро на 100%
        is_full = False
        b_match = re.search(r'🪣\s*(\d+)/(\d+)', main_msg.text or "")
        if not b_match:
            for row in (main_msg.buttons or []):
                for btn in row:
                    if "🪣" in getattr(btn, "text", ""):
                        b_match = re.search(r'(\d+)/(\d+)', btn.text)
                        if b_match: break
                if b_match: break
        
        if b_match:
            is_full = int(b_match.group(1)) == int(b_match.group(2))

        btn_bucket = None
        for row in (main_msg.buttons or []):
            for btn in row:
                if "🪣" in btn.text or "ведро" in btn.text.lower():
                    btn_bucket = btn
                    break
            if btn_bucket: break
            
        if not btn_bucket:
            return main_msg
            
        # Заходим в ведро
        await self._click_and_wait(btn_bucket, mid, expected_data=b'bins')
        msg = (await self.client.get_messages(self.target_bot, ids=[mid]))[0]
        
        while True:
            if not msg or not msg.buttons:
                break
                
            small_fishes = []
            for row in msg.buttons:
                for btn in row:
                    text = btn.text.lower()
                    if " г " in text and "кг" not in text and getattr(btn, "data", b"") and b"bins" in btn.data:
                        small_fishes.append(btn)
                
            if not small_fishes:
                logger.info("[FISH] Мелкой рыбы больше нет, выхожу из ведра")
                back_btn = None
                for row in msg.buttons:
                    for btn in row:
                        if "назад" in btn.text.lower() or "👈🏻" in btn.text or "main" in getattr(btn, "data", b"").decode('utf-8'):
                            back_btn = btn
                            break
                    if back_btn: break
                
                if back_btn:
                    await self._click_and_wait(back_btn, mid, expected_data=b'main')
                    msg = (await self.client.get_messages(self.target_bot, ids=[mid]))[0]
                break
                
            # Если ведро фулл и мелкая рыба только 1 - оставляем её для цеха
            if is_full and len(small_fishes) == 1:
                logger.info("[FISH] Ведро заполнено и мелкая рыба только одна. Оставляем её для рыбо-цеха")
                back_btn = None
                for row in msg.buttons:
                    for btn in row:
                        if "назад" in btn.text.lower() or "👈🏻" in btn.text or "main" in getattr(btn, "data", b"").decode('utf-8'):
                            back_btn = btn
                            break
                    if back_btn: break
                
                if back_btn:
                    await self._click_and_wait(back_btn, mid, expected_data=b'main')
                    msg = (await self.client.get_messages(self.target_bot, ids=[mid]))[0]
                break

            small_fish_btn = small_fishes[0]
            fish_text = small_fish_btn.text.strip()
            logger.info(f"[FISH] Нашел мелкую рыбу: {small_fish_btn.text}, открываю...")
            await self._click_and_wait(small_fish_btn, mid)
            msg = (await self.client.get_messages(self.target_bot, ids=[mid]))[0]
            
            if msg and msg.buttons:
                drop_btn = None
                for row in msg.buttons:
                    for btn in row:
                        if "отпустить" in btn.text.lower() or "выбросить" in btn.text.lower():
                            drop_btn = btn
                            break
                    if drop_btn: break
                    
                if drop_btn:
                    logger.info("[FISH] Выбрасываю/Отпускаю мелочь...")
                    
                    fish_name = msg.text.split('\n')[0].strip() if msg.text else fish_text.split()[0]
                    weight_match = re.search(r'(\d+[.,]?\d*)\s*(?:г|кг)', msg.text or fish_text)
                    fish_weight = weight_match.group(0).strip() if weight_match else "? г"
                    notify_text = f"💦<b>{fish_name}</b>, {fish_weight}"
                        
                    try:
                        notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                        await self.client.send_message(notify_id, notify_text, parse_mode="html")
                    except Exception as e:
                        logger.error(f"[FISH] Ошибка отправки уведомления: {e}")

                    await self._click_and_wait(drop_btn, mid, expected_data=b'bins')
                    
                    # Как только выбросили первую рыбу - ведро больше не полное
                    is_full = False
                    
                    await asyncio.sleep(random.uniform(2, 3))
                    
                    for _ in range(5):
                        msg = (await self.client.get_messages(self.target_bot, ids=[mid]))[0]
                        if msg and msg.buttons and any("👈🏻" in getattr(b, "text", "") or " г " in getattr(b, "text", "").lower() for r in msg.buttons for b in r):
                            break
                        await asyncio.sleep(1)
                else:
                    back_btn = None
                    for row in msg.buttons:
                        for btn in row:
                            if "назад" in btn.text.lower() or "👈🏻" in btn.text:
                                back_btn = btn
                                break
                    if back_btn:
                        await self._click_and_wait(back_btn, mid, expected_data=b'bins')
                        msg = (await self.client.get_messages(self.target_bot, ids=[mid]))[0]
                    else:
                        break
        return msg

    async def _drop_rotten_fish(self):
        await self.client.send_message(self.target_bot, "Муф")
        await asyncio.sleep(random.uniform(2, 3))
        msg = await self._get_last_bot_msg()
        if not msg: return
        main_msg_id = msg.id
        
        for row in (msg.buttons or []):
            for btn in row:
                if "ведро" in btn.text.lower():
                    msg = await self._click_and_wait(btn, main_msg_id, expected_data=b'bins')
                    break
        
        if msg and not isinstance(msg, str) and msg.buttons:
            for row in msg.buttons:
                for btn in row:
                    if "☠️" in btn.text:
                        rotten_fish_text = btn.text.strip()
                        msg = await self._click_and_wait(btn, main_msg_id, expected_data=b'drop')
                        if msg and not isinstance(msg, str) and msg.buttons:
                            for r in msg.buttons:
                                for b in r:
                                    if "выбросить" in b.text.lower() or "отпустить" in b.text.lower():
                                        await self._click_and_wait(b, main_msg_id)
                                        logger.info("[FISH] Выбросил гнилую рыбу")
                                        
                                        fish_name = msg.text.split('\n')[0].strip() if msg.text else rotten_fish_text.replace("☠️", "").strip()
                                        weight_match = re.search(r'(\d+[.,]?\d*)\s*(?:г|кг)', msg.text or rotten_fish_text)
                                        fish_weight = weight_match.group(0).strip() if weight_match else "? г"
                                        notify_text = f"🍃<b>{fish_name}</b>, {fish_weight}"
                                            
                                        try:
                                            notify_id = await self.lookup("ControlPanelMod").get_notify_id()
                                            await self.client.send_message(notify_id, notify_text, parse_mode="html")
                                        except Exception as e:
                                            logger.error(f"[FISH] Ошибка отправки уведомления: {e}")
                                            
                                        return

    async def _refill_water(self, msg):
        if not msg or not msg.buttons: return
        for row in msg.buttons:
            for btn in row:
                if btn.text.startswith("💧"):
                    try:
                        target_chat_id = await self.lookup("ControlPanelMod").get_notify_id() 
                        water_val = int(re.sub(r'[^\d]', '', btn.text))
                        if water_val == 0:
                            await self._click_and_wait(btn, msg.id)
                            await self._click_and_wait(btn, msg.id)
                            await self.client.send_message(target_chat_id, "💧 -2 водички")
                        elif water_val <= 50:
                            await self._click_and_wait(btn, msg.id)
                            await self.client.send_message(target_chat_id, "💧 -1 водичка")
                    except Exception: pass
                    return

    # ================== ИНТЕРФЕЙС / НАСТРОЙКИ (.autop) ==================

    async def get_status_text(self):
        enabled = self.db.get(self.strings["name"], "enabled", False)
        return f"{self.EMOJI} {self.strings['name']}: {'✅' if enabled else '❌'}"

    async def render_settings(self, call, menu="main"):
        if menu == "main":
            spot = self.db.get(self.strings["name"], "spot")
            gear = self.db.get(self.strings["name"], "gear")
            bait = self.db.get(self.strings["name"], "bait")
            food = self.db.get(self.strings["name"], "food")

            active_gear = [k for k, v in {"🛹": gear.get("skate"), "🧦": gear.get("socks")}.items() if v]
            gear_str = "🎣, 🗺" + (f", {', '.join(active_gear)}" if active_gear else "")

            active_bait = [emoji for emoji, state in bait.items() if state]
            active_food = [emoji for emoji, state in food.items() if state]
            beer_status = self.db.get(self.strings["name"], "beer", False)
            drop_small_fish = self.db.get(self.strings["name"], "drop_small_fish", False)
            
            text = (
                f"<b>{self.EMOJI} Настройки рыбалки</b>\n\n"
                f"📍 <b>Локация:</b> <code>{spot}</code>\n"
                f"🎒 <b>Экипировка:</b> {gear_str}\n"
                f"🪱 <b>Наживка:</b> {', '.join(active_bait)}\n"
                f"🥦 <b>Еда:</b> {', '.join(active_food)}\n"
                f"🍺 <b>Пиво:</b> {'✅' if beer_status else '❌'}\n"
                f"🍃 <b>Мелочь:</b> {'✅' if drop_small_fish else '❌'}\n\n"
                f"<i>Выберите категорию для настройки:</i>"
            )

            buttons = [
                [{'text': '📍 Локация', 'callback': self.render_settings, 'args': ('spot',)},
                {'text': '🎒 Экипировка', 'callback': self.render_settings, 'args': ('gear',)}],
                [{'text': '🪱 Наживка', 'callback': self.render_settings, 'args': ('bait',)},
                {'text': '🥦 Еда', 'callback': self.render_settings, 'args': ('food',)}],
                [{'text': '🆙 Скиллы', 'callback': self.render_settings, 'args': ('lvlup_priority',)},
                {'text': '⚙️ Спец', 'callback': self.render_settings, 'args': ('special',)}],
                [{'text': f"🕰️ Случайное время {'✅' if self.db.get(self.strings['name'], 'random_schedule', False) else '❌'}",
                  'callback': self.lookup("ControlPanelMod").toggle_random_schedule, "args": ("fish",)}],
                [{'text': '⬅️ Назад', 'callback': self.lookup("ControlPanelMod").open_module_menu, "args": ("fish",)}]
            ]
            await call.edit(text, reply_markup=buttons)

        elif menu == "spot":
            spot = self.db.get(self.strings["name"], "spot")
            text = f"<b>📍 Выберите локацию:</b>\n<i>Сейчас выбрано: {spot}</i>"
            buttons = [
                [{'text': '🏝 Причал', 'callback': self.set_spot, 'args': ('🏝 Причал',)},
                 {'text': '☘️ Болото', 'callback': self.set_spot, 'args': ('☘️ Болото',)}],
                [{'text': '🍄 Грибозеро', 'callback': self.set_spot, 'args': ('🍄 Грибозеро',)},
                 {'text': '🧊 Ледник', 'callback': self.set_spot, 'args': ('🧊 Ледник',)}],
                [{'text': '⬅️ Назад', 'callback': self.render_settings, 'args': ('main',)}]
            ]
            await call.edit(text, reply_markup=buttons)

        elif menu == "gear":
            gear = self.db.get(self.strings["name"], "gear")
            text = f"<b>🎒 Настройка экипировки:</b>\n<i>Удочка и карта надеваются всегда!\nОстальное по желанию:</i>"
            buttons = [
                [{'text': f"🛹 Скейт: {'✅' if gear['skate'] else '❌'}", 'callback': self.toggle_dict, 'args': ('gear', 'skate')}],
                [{'text': f"🧦 Носочки: {'✅' if gear['socks'] else '❌'}", 'callback': self.toggle_dict, 'args': ('gear', 'socks')}],
                [{'text': '⬅️ Назад', 'callback': self.render_settings, 'args': ('main',)}]
            ]
            await call.edit(text, reply_markup=buttons)

        elif menu == "bait":
            bait = self.db.get(self.strings["name"], "bait")
            text = f"<b>🪱 Настройка наживки:</b>\n<i>Внимание: минимум одна наживка\nдолжна быть включена!</i>"
            buttons = [
                [{'text': f"🪱 Черви: {'✅' if bait['🪱'] else '❌'}", 'callback': self.toggle_dict, 'args': ('bait', '🪱')}],
                [{'text': f"🦋 Бабочки: {'✅' if bait['🦋'] else '❌'}", 'callback': self.toggle_dict, 'args': ('bait', '🦋')}],
                [{'text': '⬅️ Назад', 'callback': self.render_settings, 'args': ('main',)}]
            ]
            await call.edit(text, reply_markup=buttons)

        elif menu == "food":
            food = self.db.get(self.strings["name"], "food")
            text = f"<b>🥦 Настройка еды:</b>\n<i>Внимание: коровка должна что-то кушать\n(минимум 1 вариант)!</i>"
            buttons = [
                [{'text': f"🍵 Холи-суп {'✅' if food['🍵'] else '❌'}", 'callback': self.toggle_dict, 'args': ('food', '🍵')},
                 {'text': f"🌿 Травка {'✅' if food['🌿'] else '❌'}", 'callback': self.toggle_dict, 'args': ('food', '🌿')}],
                [{'text': f"🥤 Милк-шейк {'✅' if food['🥤'] else '❌'}", 'callback': self.toggle_dict, 'args': ('food', '🥤')},
                 {'text': f"🥦 Брокколи {'✅' if food['🥦'] else '❌'}", 'callback': self.toggle_dict, 'args': ('food', '🥦')}],
                [{'text': f"🍗 Нагетс {'✅' if food['🍗'] else '❌'}", 'callback': self.toggle_dict, 'args': ('food', '🍗')}],
                [{'text': '⬅️ Назад', 'callback': self.render_settings, 'args': ('main',)}]
            ]
            await call.edit(text, reply_markup=buttons)

        elif menu == "lvlup_priority":
            priorities = self.db.get(self.strings["name"], "lvlup_priority", [])
            text = "<b>🆙 Приоритеты прокачки скиллов:</b>\n<i>Чем выше в списке, тем приоритетнее. Нажимай на кнопку со скиллом, чтобы поднять его на 1 позицию вверх.</i>\n\n"
            for i, skill in enumerate(priorities, 1):
                text += f"<b>{i}.</b> {skill}\n"
            
            buttons = utils.chunks([
                {'text': f"⬆️ {skill.split(' ')[0]}", 'callback': self.move_priority_up, 'args': (skill,)}
                for skill in priorities
            ], 3)
            buttons.append([{'text': '⬅️ Назад', 'callback': self.render_settings, 'args': ('main',)}])
            await call.edit(text, reply_markup=buttons)

        elif menu == "special":
            beer_status = self.db.get(self.strings["name"], "beer", False)
            drop_small_fish = self.db.get(self.strings["name"], "drop_small_fish", False)
            text = (
                f"<b>⚙️ Специальные настройки:</b>\n\n"
                f"<i>🍺 <b>Автопиво</b> – бот будет автоматически пить пиво, чтобы сбросить время ожидания (КД)\n\n"
                f"<b>🍃 Мелочь</b> – бот будет заходить в ведро и выбрасывать рыбу весом от 0 до 999 грамм</i>"
            )
            buttons = [
                [{'text': f"🍺 Пиво {'✅' if beer_status else '❌'}", 'callback': self.toggle_beer}],
                [{'text': f"🍃 Мелочь {'✅' if drop_small_fish else '❌'}", 'callback': self.toggle_drop_small}],
                [{'text': '⬅️ Назад', 'callback': self.render_settings, 'args': ('main',)}]
            ]
            await call.edit(text, reply_markup=buttons)

    async def set_spot(self, call, spot_name):
        self.db.set(self.strings["name"], "spot", spot_name)
        await call.answer(f"✅ Локация изменена на: {spot_name}")
        await self.render_settings(call, "spot")

    async def toggle_dict(self, call, dict_name, key):
        data = self.db.get(self.strings["name"], dict_name)
        if data[key] is True:
            active_count = sum(1 for v in data.values() if v)
            if active_count <= 1:
                if dict_name == "food":
                    await call.answer("❌ Должна быть выбрана хотя бы одна еда")
                    return
                elif dict_name == "bait":
                    await call.answer("❌ Должна быть выбрана хотя бы одна наживка")
                    return
        data[key] = not data[key]
        self.db.set(self.strings["name"], dict_name, data)
        await self.render_settings(call, dict_name)

    async def toggle_beer(self, call):
        current = self.db.get(self.strings["name"], "beer", False)
        self.db.set(self.strings["name"], "beer", not current)
        await call.answer(f"🍺 Автопиво {'Включено' if not current else 'Выключено'}")
        await self.render_settings(call, "main")

    async def move_priority_up(self, call, skill):
        priorities = self.db.get(self.strings["name"], "lvlup_priority", [])
        if skill in priorities:
            idx = priorities.index(skill)
            if idx > 0:
                priorities[idx], priorities[idx-1] = priorities[idx-1], priorities[idx]
                self.db.set(self.strings["name"], "lvlup_priority", priorities)
        await self.render_settings(call, "lvlup_priority")

    async def toggle_drop_small(self, call):
        current = self.db.get(self.strings["name"], "drop_small_fish", False)
        self.db.set(self.strings["name"], "drop_small_fish", not current)
        await call.answer(f"🍃💦 Выбрасывание мелкой рыбы (0-999 г) {'Включено' if not current else 'Выключено'}")
        await self.render_settings(call, "main")