# Auto_TaskManager.py
from .. import loader
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging, time, random

logger = logging.getLogger("TaskManager")

@loader.tds
class TaskManagerMod(loader.Module):
    """Распределение очереди между модулями"""
    strings = {"name": "TaskManager"}

    def __init__(self):
        self.wait_queue = []
        self._logged_schedules = set()
        
    async def client_ready(self, client, db):
        self.db = db
        self.db.set("TaskManager", "locks", {})
        self.wait_queue = [] 

        modules_list = ["AutoWellMod", "GryadkaMod", "GovnoMod", "CraftMod", "MuzMod", "ChickMod", "FishMod"]
        for module_name in modules_list:
            module = self.lookup(module_name)
            if module and hasattr(module, "strings") and "name" in module.strings:
                self.db.set(module.strings["name"], "schedule_date", None)

        try:
            self.tz = ZoneInfo("Europe/Kiev") 
        except Exception:
            self.tz = timezone.utc

    async def acquire_lock(self, module_name: str) -> bool:
        locks = self.db.get("TaskManager", "locks", {})
        current_owner = next(iter(locks), None)

        if current_owner == module_name:
            return True

        if current_owner is not None:
            return False

        if module_name not in self.wait_queue:
            self.wait_queue.append(module_name)
            if len(self.wait_queue) > 1:
                logger.debug(f"🚦 {module_name} встал в очередь")

        if self.wait_queue[0] == module_name:
            self.wait_queue.pop(0)
            locks[module_name] = time.time()
            self.db.set("TaskManager", "locks", locks)
            logger.info(f"🟢 {module_name} получил доступ")
            return True
        return False

    async def release_lock(self, module_name):
        locks = self.db.get("TaskManager", "locks", {})
        
        if module_name in locks:
            del locks[module_name]
            self.db.set("TaskManager", "locks", locks)
            logger.info(f"⚪️ {module_name} освободил место")
        
        if module_name in self.wait_queue:
            self.wait_queue.remove(module_name)

    async def is_well_soon(self, minutes_before=2):
        well_mod = self.lookup("AutoWellMod")
        if not well_mod or not hasattr(well_mod, 'next_run'):
            return False
        return 0 < well_mod.next_run - time.time() < (minutes_before * 60)
    
    async def check_schedule(self, module):
        module_name = module.strings["name"]
        db = module.db

        if not db.get(module_name, "random_schedule", False):
            return True

        now_local = datetime.now(self.tz)
        today = now_local.date()
        today_str = today.isoformat()
        
        schedule_date = db.get(module_name, "schedule_date", None)
        log_key = f"{module_name}_{today_str}"

        if schedule_date != today_str:
            start_dt = now_local.replace(hour=6, minute=random.randint(0, 59), second=random.randint(0, 59), microsecond=random.randint(0, 999999))

            end_hour = random.choice([23, 0])
            end_minute = random.randint(0, 59)
            end_dt = now_local.replace(hour=end_hour, minute=end_minute, second=random.randint(0, 59), microsecond=random.randint(0, 999999))
            if end_hour == 0: end_dt += timedelta(days=1)

            start_ts = start_dt.timestamp()
            end_ts = end_dt.timestamp()

            db.set(module_name, "schedule_date", today_str)
            db.set(module_name, "schedule_start_ts", start_ts)
            db.set(module_name, "schedule_end_ts", end_ts)

            old_keys = [k for k in self._logged_schedules if k.startswith(module_name)]
            for k in old_keys: self._logged_schedules.remove(k)
        else:
            start_ts = db.get(module_name, "schedule_start_ts")
            end_ts = db.get(module_name, "schedule_end_ts")

        if log_key not in self._logged_schedules:
            start_dt_obj = datetime.fromtimestamp(start_ts, tz=self.tz)
            end_dt_obj = datetime.fromtimestamp(end_ts, tz=self.tz)
            logger.info(f"[{module_name}] 🗓 Расписание на сегодня: {start_dt_obj.strftime('%H:%M:%S')} - {end_dt_obj.strftime('%H:%M:%S')}")
            self._logged_schedules.add(log_key)
            
        return start_ts <= time.time() < end_ts
