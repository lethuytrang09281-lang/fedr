#!/usr/bin/env python3
"""FEDRESURS RADAR - Health Check Script
Проверка всех компонентов системы"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Добавляем src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger
from src.config import settings
from src.client.api import EfrsbClient
from src.services.xml_parser import XMLParser


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
            hasattr(settings, 'EFRSB_ENV') and settings.EFRSB_ENV in ["DEMO", "PROD"],
            f"Current: {getattr(settings, 'EFRSB_ENV', 'NOT SET')}"
        )

        # API credentials
        has_creds = bool(getattr(settings, 'EFRSB_LOGIN', None) and getattr(settings, 'EFRSB_PASSWORD', None))
        self.check(
            "API Credentials",
            has_creds,
            f"Login: {getattr(settings, 'EFRSB_LOGIN', 'NOT SET')}"
        )

        # Rate limiter
        self.check(
            "Rate Limit Config",
            1 <= getattr(settings, 'MAX_REQS_PER_SECOND', 0) <= 8,
            f"Limit: {getattr(settings, 'MAX_REQS_PER_SECOND', 'NOT SET')} req/sec"
        )

        # Database URL
        self.check(
            "Database Config",
            all(hasattr(settings, attr) for attr in ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']),
            f"Host: {getattr(settings, 'DB_HOST', 'NOT SET')}, Port: {getattr(settings, 'DB_PORT', 'NOT SET')}"
        )

    async def check_api(self):
        """Проверка API клиента"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("🌐 API CLIENT CHECK")
        logger.info("=" * 60)

        try:
            client = EfrsbClient()
            # Авторизация
            await client.login()
            has_token = client._token is not None
            self.check(
                "JWT Authorization",
                has_token,
                f"Token: {client._token[:30]}..." if has_token else "No token"
            )

            # Тестовый запрос
            date_end = datetime.now(timezone.utc)
            date_begin = date_end - timedelta(days=7)

            result = await client.get_trade_messages(
                date_start=date_begin.strftime('%Y-%m-%dT%H:%M:%S'),
                date_end=date_end.strftime('%Y-%m-%dT%H:%M:%S'),
                limit=5
            )

            total = getattr(result, 'total', 0)
            retrieved = len(getattr(result, 'pageData', []))

            self.check(
                "API Request (last 7 days)",
                total >= 0,
                f"Total: {total}, Retrieved: {retrieved}"
            )

            # Проверка структуры ответа
            has_page_data = hasattr(result, 'pageData')
            self.check(
                "Response Structure",
                has_page_data,
                "pageData key present" if has_page_data else "Missing pageData"
            )

            await client.close()

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
                host=getattr(settings, 'DB_HOST', 'localhost'),
                port=getattr(settings, 'DB_PORT', 5432),
                database=getattr(settings, 'DB_NAME', 'fedresurs_db'),
                user=getattr(settings, 'DB_USER', 'postgres'),
                password=getattr(settings, 'DB_PASSWORD', 'password'),
                timeout=10
            )

            self.check(
                "PostgreSQL Connection",
                True,
                f"{getattr(settings, 'DB_HOST', 'localhost')}:{getattr(settings, 'DB_PORT', 5432)}/{getattr(settings, 'DB_NAME', 'fedresurs_db')}"
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
            self.check(
                "Database Schema",
                len(table_names) > 0,
                f"Tables: {len(table_names)} ({', '.join(table_names[:5])}...)"
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