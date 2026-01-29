from src.services.xml_parser import XMLParserService
from src.database.models import Trade, Lot
import asyncio


def test_xml_parsing():
    # Пример XML-контента для тестирования
    sample_xml_bidding = '''<?xml version="1.0" encoding="UTF-8"?>
<biddingInvitation type="BiddingInvitation">
    <notificationNumber>TEST-2023-001</notificationNumber>
    <publishDate>2023-10-01T10:00:00Z</publishDate>
    <lots>
        <lot>
            <description>Жилая недвижимость - МКД в центре города</description>
            <startPrice>5000000.00</startPrice>
            <status>active</status>
        </lot>
        <lot>
            <description>Земельный участок под ИЖС</description>
            <startPrice>1500000.00</startPrice>
            <status>active</status>
        </lot>
    </lots>
</biddingInvitation>'''
    
    sample_xml_auction = '''<?xml version="1.0" encoding="UTF-8"?>
<auction2 type="Auction2">
    <tradeNumber>TEST-2023-002</tradeNumber>
    <createDate>2023-10-02T11:00:00Z</createDate>
    <item>
        <name>Коммерческая недвижимость</name>
        <initialPrice>10000000.00</initialPrice>
        <state>active</state>
    </item>
</auction2>'''
    
    print("Тестируем парсер XML для типа BiddingInvitation:")
    trade, lots = XMLParserService.parse_xml_content(sample_xml_bidding)
    print(f"Trade number: {trade.trade_number}")
    print(f"Number of lots: {len(lots)}")
    for i, lot in enumerate(lots):
        print(f"  Lot {i+1}: {lot.description[:50]}..., Price: {lot.start_price}")
    
    print("\nТестируем парсер XML для типа Auction2:")
    trade, lots = XMLParserService.parse_xml_content(sample_xml_auction)
    print(f"Trade number: {trade.trade_number}")
    print(f"Number of lots: {len(lots)}")
    for i, lot in enumerate(lots):
        print(f"  Lot {i+1}: {lot.description[:50]}..., Price: {lot.start_price}")


if __name__ == "__main__":
    test_xml_parsing()