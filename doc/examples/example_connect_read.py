# doc/examples/example_connect_read.py

import asyncio
import logging
from typing import Any

from uhf_rfid.core.reader import Reader
from uhf_rfid.core.status import ConnectionStatus
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph import constants as cph_const
from uhf_rfid.transport.serial_async import SerialTransport
# Ракоментирайте долния ред и коментирайте горния, за да използвате TCP
# from uhf_rfid.transport.tcp_async import TcpTransport

# Настройка на логване (по желание)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("ConnectReadExample")

# --- Конфигурация ---
# Променете според вашата настройка
SERIAL_PORT = 'COM3'  # За Windows. За Linux може да е '/dev/ttyUSB0' или подобно.
SERIAL_BAUD_RATE = 115200

# Алтернативно, за TCP връзка:
# READER_HOST = '192.168.1.178' # IP адрес на четеца
# READER_PORT = 6000           # TCP порт на четеца


async def tag_callback(frame_type: int, address: int, frame_code: int, params: Any):
    """Асинхронна функция, която се извиква при получаване на данни за таг."""
    logger.info(f"Получена нотификация: Code={frame_code:#04x}, Addr={address:#06x}")
    
    # Проверка дали нотификацията е за таг (0x80 или 0x81)
    if frame_code in [cph_const.NOTIF_TAG_UPLOADED, cph_const.NOTIF_OFFLINE_TAG_UPLOADED]:
        try:
            # Данните за тага са в TAG_SINGLE_TAG -> TAG_EPC
            tag_data = params.get(cph_const.TAG_SINGLE_TAG, {})
            epc = tag_data.get(cph_const.TAG_EPC, "N/A")
            rssi_val = tag_data.get(cph_const.TAG_RSSI, None)
            rssi_str = f", RSSI: {rssi_val}" if rssi_val is not None else ""
            logger.info(f"  TAG Прочетен: EPC={epc}{rssi_str}")
        except Exception as e:
            logger.error(f"  Грешка при обработка на данни от таг: {e} - Данни: {params}")
    else:
        logger.info(f"  Друга нотификация: {params}")

async def main():
    """Главна асинхронна функция."""
    
    # --- Създаване на Транспорт --- 
    # За Сериен порт:
    transport = SerialTransport(port=SERIAL_PORT, baudrate=SERIAL_BAUD_RATE)
    # За TCP:
    # transport = TcpTransport(host=READER_HOST, port=READER_PORT)
    
    # --- Създаване на Протокол ---
    protocol = CPHProtocol()
    
    # --- Създаване на Четец ---
    reader = Reader(transport, protocol, response_timeout=3.0)
    
    # --- Callback за промяна на статуса (по желание) ---
    def status_changed(status: ConnectionStatus):
        logger.info(f"Статус на връзката променен: {status}")
    reader.set_status_change_callback(status_changed)

    try:
        logger.info("Свързване към четеца...")
        await reader.connect()
        logger.info("Успешно свързване!")

        # --- Регистриране на callback за тагове ---
        logger.info("Регистриране на callback за тагове...")
        await reader.register_tag_notify_callback(tag_callback)
        
        # --- Стартиране на инвентаризация ---
        logger.info("Стартиране на инвентаризация...")
        await reader.start_inventory()
        
        # --- Изчакване за прочитане на тагове ---
        logger.info("Четене на тагове за 10 секунди...")
        await asyncio.sleep(10)
        
        # --- Спиране на инвентаризация ---
        logger.info("Спиране на инвентаризация...")
        await reader.stop_inventory()
        logger.info("Инвентаризацията е спряна.")

        # Почивка преди разкачане
        await asyncio.sleep(1)

    except Exception as e:
        logger.exception(f"Възникна грешка: {e}")
    finally:
        logger.info("Разкачане от четеца...")
        if reader.is_connected:
            # Дерегистриране на callback преди разкачане (добра практика)
            try:
                 await reader.unregister_callback(tag_callback)
            except Exception as e:
                 logger.error(f"Грешка при дерегистрация на callback: {e}")
            await reader.disconnect()
        logger.info("Връзката е затворена.")

if __name__ == "__main__":
    asyncio.run(main()) 