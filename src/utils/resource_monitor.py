"""
Мониторинг ресурсов сервера с автоматическим throttling
"""
import psutil
import asyncio
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Мониторинг CPU/RAM с автоматическим throttling"""
    
    def __init__(
        self,
        cpu_threshold: float = 80.0,
        cpu_critical: float = 150.0,
        ram_threshold: float = 85.0,
        ram_critical: float = 95.0,
        check_interval: int = 5
    ):
        self.cpu_threshold = cpu_threshold
        self.cpu_critical = cpu_critical
        self.ram_threshold = ram_threshold
        self.ram_critical = ram_critical
        self.check_interval = check_interval
        
        self.throttle_active = False
        self.critical_mode = False
        
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запустить мониторинг"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("🔍 Resource Monitor started")
    
    async def stop(self):
        """Остановить мониторинг"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Resource Monitor stopped")
    
    async def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self._monitoring:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                ram_percent = psutil.virtual_memory().percent
                
                logger.info(f"📊 Resources: CPU={cpu_percent:.1f}%, RAM={ram_percent:.1f}%")
                
                if cpu_percent >= self.cpu_critical or ram_percent >= self.ram_critical:
                    if not self.critical_mode:
                        self.critical_mode = True
                        logger.error(f"🚨 CRITICAL! CPU={cpu_percent}%, RAM={ram_percent}%")
                
                elif cpu_percent >= self.cpu_threshold or ram_percent >= self.ram_threshold:
                    if not self.throttle_active:
                        self.throttle_active = True
                        logger.warning(f"⚠️ THROTTLE ON: CPU={cpu_percent}%, RAM={ram_percent}%")
                
                else:
                    if self.throttle_active:
                        self.throttle_active = False
                        logger.info("✅ THROTTLE OFF: Resources normalized")
                    if self.critical_mode:
                        self.critical_mode = False
                        logger.info("✅ CRITICAL MODE OFF")
                
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    def should_pause(self) -> bool:
        """Нужно ли приостановить работу?"""
        return self.throttle_active or self.critical_mode
    
    def should_stop(self) -> bool:
        """Нужно ли полностью остановиться?"""
        return self.critical_mode
    
    async def wait_if_needed(self):
        """Подождать если ресурсы перегружены"""
        if self.critical_mode:
            logger.warning("⏸️ CRITICAL MODE: Pausing for 60 seconds...")
            await asyncio.sleep(60)
        elif self.throttle_active:
            logger.info("⏸️ THROTTLE: Pausing for 10 seconds...")
            await asyncio.sleep(10)
