# doc/examples/example_memory_ops.py

import asyncio
import logging

from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import CommandError, UhfRfidError
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph import constants as cph_const # За MEM_BANK_*
from uhf_rfid.transport.serial_async import SerialTransport
# from uhf_rfid.transport.tcp_async import TcpTransport

# Настройка на логване
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("MemoryOpsExample")

# --- Конфигурация ---
SERIAL_PORT = 'COM3' # Заменете с вашия порт
SERIAL_BAUD_RATE = 115200
# READER_HOST = '192.168.1.178'
# READER_PORT = 6000

# --- Параметри за четене/запис ---
# ВАЖНО: Променете според нуждите и спецификата на тага
MEMORY_BANK = cph_const.MEM_BANK_USER # Банка памет (USER)
START_WORD_ADDRESS = 0               # Начален адрес (в думи, 1 word = 2 bytes)
NUM_WORDS_TO_RW = 4                  # Брой думи за четене/запис (=> 8 байта)
# Парола за достъп (4 байта). Нули (b'\x00\x00\x00\x00') е често използвана по подразбиране.
ACCESS_PASSWORD = b'\x00\x00\x00\x00' 
# Данни за запис (трябва да са NUM_WORDS_TO_RW * 2 байта)
DATA_TO_WRITE = b'\x11\x22\x33\x44\xAA\xBB\xCC\xDD'

async def main():
    transport = SerialTransport(port=SERIAL_PORT, baudrate=SERIAL_BAUD_RATE)
    # transport = TcpTransport(host=READER_HOST, port=READER_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport, protocol)

    async with reader: # Автоматично connect/disconnect
        logger.info("Успешно свързване!")
        
        logger.info(f"Ще се опитаме да четем/пишем в банка {MEMORY_BANK}, адрес {START_WORD_ADDRESS}, {NUM_WORDS_TO_RW} думи.")
        logger.warning("Уверете се, че има RFID таг в обхвата на четеца!")
        await asyncio.sleep(2) # Кратка пауза
        
        try:
            # --- Четене от паметта на таг ---
            logger.info("Опит за четене от паметта на тага...")
            read_data = await reader.read_tag_memory(
                bank=MEMORY_BANK,
                word_ptr=START_WORD_ADDRESS,
                word_count=NUM_WORDS_TO_RW,
                access_password=ACCESS_PASSWORD
            )
            logger.info(f"Успешно прочетени данни: {read_data.hex(' ').upper()}")
            
            await asyncio.sleep(1)
            
            # --- Запис в паметта на таг ---
            logger.info(f"Опит за запис на данни: {DATA_TO_WRITE.hex(' ').upper()}...")
            await reader.write_tag_memory(
                bank=MEMORY_BANK,
                word_ptr=START_WORD_ADDRESS,
                data=DATA_TO_WRITE,
                access_password=ACCESS_PASSWORD
            )
            logger.info("Командата за запис е изпратена успешно.")
            
            await asyncio.sleep(1)
            
            # --- Проверка след запис ---
            logger.info("Повторно четене за проверка...")
            data_after_write = await reader.read_tag_memory(
                bank=MEMORY_BANK,
                word_ptr=START_WORD_ADDRESS,
                word_count=NUM_WORDS_TO_RW,
                access_password=ACCESS_PASSWORD
            )
            logger.info(f"Прочетени данни след запис: {data_after_write.hex(' ').upper()}")
            
            if data_after_write == DATA_TO_WRITE:
                logger.info("Проверката успешна! Данните са записани коректно.")
            else:
                logger.error("ГРЕШКА ПРИ ПРОВЕРКА! Прочетените данни не съвпадат със записаните.")

        except CommandError as e:
            logger.error(f"Операцията с паметта неуспешна със статус: {e.status_code:#04x} ({e.get_status_message()})")
            logger.error("Възможни причини: Грешна парола, грешен адрес/банка, тагът не е в обхват, тагът е заключен.")
        except UhfRfidError as e:
             logger.error(f"Грешка в библиотеката или протокола: {e}")
        except Exception as e:
            logger.exception(f"Възникна неочаквана грешка: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 