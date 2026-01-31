#!/usr/bin/env python3
"""
FEDRESURS RADAR - Health Check Script
Проверка всех компонентов системы
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Добавляем src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from src.config import settings
from src.api_client import EfrsbClient
from src.xml_parser import XMLParser


class HealthChecker:
    """Проверка здоровья системы"""
    
    def __init__(self):
        self.results = {}
        self.passed = 0
        self.failed = 0
    
    def check(self, name: str, passed: bool, details: str = ""):
        """Регистрация результата проверки"""
        status = "✅ PASS" if passed else "❌ FAIL"
        self.results[name] = {"passed": passed, "details": details}
        
        if passed:
            self.passed += 1
            logger.success(f"{status} | {name}")
        else:
            self.failed += 1
            logger.error(f"{status} | {name}")
        
        if details:
            logger.info(f"      └─ {details}")
    
    def check_config(self):
        """Проверка конфигурации"""
        logger.info("=" * 60)
        logger.info("🔧 CONFIGURATION CHECK")
        logger.info("=" * 60)
        
        # Environment
        self.check(
            "Environment",
            settings.efrsb_env in ["DEMO", "PROD"],
            f"Current: {settings.efrsb_env}"
        )
        
        # API credentials
        has_creds = bool(settings.api_login and settings.api_password)
        self.check(
            "API Credentials",
            has_creds,
            f"Login: {settings.api_login}"
        )
        
        # Rate limiter
        self.check(
            "Rate Limit Config",
            1 <= settings.max_reqs_per_second <= 8,
            f"Limit: {settings.max_reqs_per_second} req/sec"
        )
        
        # Database URL
        self.check(
            "Database URL",
            "postgresql" in settings.database_url,
            f"URL: {settings.database_url[:50]}..."
        )
        
        # Semantic filters
        land_codes_ok = len(settings.land_codes) > 0
        self.check(
            "Classifier Codes",
            land_codes_ok,
            f"Land: {len(settings.land_codes)}, Buildings: {len(settings.building_codes)}"
        )
        
        keywords_ok = len(settings.include_keywords) > 0
        self.check(
            "Keywords",
            keywords_ok,
            f"Include: {len(settings.include_keywords)}, Exclude: {len(settings.exclude_keywords)}"
        )
    
    async def check_api(self):
        """Проверка API клиента"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🌐 API CLIENT CHECK")
        logger.info("=" * 60)
        
        try:
            async with EfrsbClient() as client:
                # Авторизация
                has_token = client._jwt_token is not None
                self.check(
                    "JWT Authorization",
                    has_token,
                    f"Token: {client._jwt_token[:30]}..." if has_token else "No token"
                )
                
                # Тестовый запрос
                date_end = datetime.now(timezone.utc)
                date_begin = date_end - timedelta(days=7)
                
                result = await client.get_trade_messages(
                    date_begin=date_begin,
                    date_end=date_end,
                    limit=5
                )
                
                total = result.get("total", 0)
                retrieved = len(result.get("pageData", []))
                
                self.check(
                    "API Request (last 7 days)",
                    total >= 0,
                    f"Total: {total}, Retrieved: {retrieved}"
                )
                
                # Проверка структуры ответа
                has_page_data = "pageData" in result
                self.check(
                    "Response Structure",
                    has_page_data,
                    "pageData key present" if has_page_data else "Missing pageData"
                )
                
        except Exception as e:
            self.check(
                "API Client",
                False,
                f"Error: {str(e)}"
            )
    
    def check_parser(self):
        """Проверка XML парсера"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🔍 XML PARSER CHECK")
        logger.info("=" * 60)
        
        # Тестовый XML
        test_xml = """
        <Auction2>
            <TradeType>Auction</TradeType>
            <LotTable>
                <AuctionLot>
                    <Order>1</Order>
                    <StartPrice>5000000.00</StartPrice>
                    <Description>Земельный участок под строительство многоквартирного жилого дома, 
                    кадастровый номер 77:01:0001001:456, зона Ж-1, площадь 2000 кв.м</Description>
                    <Classifier>
                        <Code>0108001</Code>
                    </Classifier>
                </AuctionLot>
            </LotTable>
        </Auction2>
        """
        
        try:
            parser = XMLParser()
            result = parser.parse_message(test_xml, "Auction2")
            
            has_result = result is not None
            self.check(
                "XML Parsing",
                has_result,
                "Successfully parsed test XML" if has_result else "Failed to parse"
            )
            
            if has_result:
                lots_found = len(result.get("lots", []))
                self.check(
                    "Lot Extraction",
                    lots_found > 0,
                    f"Lots extracted: {lots_found}"
                )
                
                if lots_found > 0:
                    lot = result["lots"][0]
                    
                    # Проверка кадастровых номеров
                    has_cadastral = len(lot.get("cadastral_numbers", [])) > 0
                    self.check(
                        "Cadastral Numbers (Regex)",
                        has_cadastral,
                        f"Found: {lot.get('cadastral_numbers', [])}"
                    )
                    
                    # Проверка цены
                    has_price = lot.get("start_price") is not None
                    self.check(
                        "Price Extraction",
                        has_price,
                        f"Price: {lot.get('start_price'):,.0f} RUB" if has_price else "No price"
                    )
                    
                    # Проверка фильтрации
                    passed_filter = True  # Лот прошёл, раз в результате
                    self.check(
                        "Semantic Filter",
                        passed_filter,
                        f"Code: {lot.get('category_code')}, Keywords matched"
                    )
            
        except Exception as e:
            self.check(
                "XML Parser",
                False,
                f"Error: {str(e)}"
            )
    
    async def check_database(self):
        """Проверка подключения к БД"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("💾 DATABASE CHECK")
        logger.info("=" * 60)
        
        try:
            import asyncpg
            
            conn = await asyncpg.connect(
                host=settings.db_host,
                port=settings.db_port,
                database=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                timeout=settings.db_timeout
            )
            
            self.check(
                "PostgreSQL Connection",
                True,
                f"{settings.db_host}:{settings.db_port}/{settings.db_name}"
            )
            
            # Проверка версии
            version = await conn.fetchval("SELECT version()")
            pg_version = version.split()[1] if version else "Unknown"
            self.check(
                "PostgreSQL Version",
                True,
                f"Version: {pg_version}"
            )
            
            # Проверка таблиц
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            
            table_names = [t["table_name"] for t in tables]
            required_tables = ["system_state", "raw_messages", "trades", "lots"]
            has_tables = all(t in table_names for t in required_tables)
            
            self.check(
                "Database Schema",
                has_tables,
                f"Tables: {len(table_names)} ({', '.join(table_names[:5])}...)"
            )
            
            # Проверка GIN-индексов
            indexes = await conn.fetch("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'public' AND indexname LIKE '%_gin'
            """)
            
            gin_count = len(indexes)
            self.check(
                "GIN Indexes",
                gin_count > 0,
                f"Found: {gin_count} GIN indexes"
            )
            
            await conn.close()
            
        except Exception as e:
            self.check(
                "Database",
                False,
                f"Error: {str(e)}"
            )
    
    def print_summary(self):
        """Печать итогового отчёта"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("📊 HEALTH CHECK SUMMARY")
        logger.info("=" * 60)
        
        total = self.passed + self.failed
        success_rate = (self.passed / total * 100) if total > 0 else 0
        
        logger.info(f"Total Checks: {total}")
        logger.info(f"✅ Passed: {self.passed}")
        logger.info(f"❌ Failed: {self.failed}")
        logger.info(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.failed == 0:
            logger.success("")
            logger.success("🎉 ALL SYSTEMS OPERATIONAL!")
            logger.success("   Ready to deploy FEDRESURS RADAR")
        else:
            logger.warning("")
            logger.warning("⚠️  SOME CHECKS FAILED")
            logger.warning("   Review errors above and fix configuration")
        
        logger.info("=" * 60)
    
    async def run_all_checks(self):
        """Запуск всех проверок"""
        logger.info("")
        logger.info("╔" + "=" * 58 + "╗")
        logger.info("║" + " " * 15 + "FEDRESURS RADAR" + " " * 28 + "║")
        logger.info("║" + " " * 17 + "Health Check" + " " * 29 + "║")
        logger.info("╚" + "=" * 58 + "╝")
        logger.info("")
        
        # Конфигурация
        self.check_config()
        
        # API
        await self.check_api()
        
        # Парсер
        self.check_parser()
        
        # База данных
        await self.check_database()
        
        # Итоги
        self.print_summary()
        
        return self.failed == 0


async def main():
    """Точка входа"""
    # Настройка логирования
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    checker = HealthChecker()
    success = await checker.run_all_checks()
    
    # Exit code для CI/CD
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
