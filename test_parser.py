from src.services.xml_parser import XMLParserService
from src.database.models import Lot
import asyncio


def test_xml_parsing():
    # Пример XML-контента для тестирования
    sample_xml_bidding = '''<?xml version="1.0" encoding="UTF-8"?>
<biddingInvitation xmlns="http://fedresurs.ru/">
    <notificationNumber>TEST-2023-001</notificationNumber>
    <publishDate>2023-10-01T10:00:00Z</publishDate>
    <LotTable>
        <AuctionLot>
            <Description>Жилая недвижимость - МКД в центре города</Description>
            <StartPrice>5000000.00</StartPrice>
            <Status>active</Status>
        </AuctionLot>
        <AuctionLot>
            <Description>Земельный участок под ИЖС</Description>
            <StartPrice>1500000.00</StartPrice>
            <Status>active</Status>
        </AuctionLot>
    </LotTable>
</biddingInvitation>'''

    sample_xml_auction = '''<?xml version="1.0" encoding="UTF-8"?>
<auction2 xmlns="http://fedresurs.ru/">
    <tradeNumber>TEST-2023-002</tradeNumber>
    <createDate>2023-10-02T11:00:00Z</createDate>
    <LotList>
        <Lot>
            <Description>Коммерческая недвижимость</Description>
            <StartPrice>10000000.00</StartPrice>
            <Status>active</Status>
        </Lot>
    </LotList>
</auction2>'''

    print("Тестируем парсер XML для типа BiddingInvitation:")
    parser = XMLParserService()
    lots_data = parser.parse_content(sample_xml_bidding, "test-guid-1")
    print(f"Number of lots: {len(lots_data)}")
    for i, lot_data in enumerate(lots_data):
        print(f"  Lot {i+1}: {lot_data.description[:50]}..., Price: {lot_data.start_price}, Classifier: {lot_data.classifier_code}")

    print("\nТестируем парсер XML для типа Auction2:")
    lots_data = parser.parse_content(sample_xml_auction, "test-guid-2")
    print(f"Number of lots: {len(lots_data)}")
    for i, lot_data in enumerate(lots_data):
        print(f"  Lot {i+1}: {lot_data.description[:50]}..., Price: {lot_data.start_price}, Classifier: {lot_data.classifier_code}")


if __name__ == "__main__":
    test_xml_parsing()