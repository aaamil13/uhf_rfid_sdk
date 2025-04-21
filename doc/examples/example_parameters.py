# doc/examples/example_parameters.py

import asyncio
import logging

from uhf_rfid.core.reader import Reader
from uhf_rfid.core.exceptions import CommandError
from uhf_rfid.protocols.cph.protocol import CPHProtocol
from uhf_rfid.protocols.cph.parameters import ExtParams # Импорт на структурата
from uhf_rfid.transport.serial_async import SerialTransport
# from uhf_rfid.transport.tcp_async import TcpTransport

# Настройка на логване
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger("ParametersExample")

# --- Конфигурация ---
SERIAL_PORT = 'COM3' # Заменете с вашия порт
SERIAL_BAUD_RATE = 115200
# READER_HOST = '192.168.1.178'
# READER_PORT = 6000

async def main():
    transport = SerialTransport(port=SERIAL_PORT, baudrate=SERIAL_BAUD_RATE)
    # transport = TcpTransport(host=READER_HOST, port=READER_PORT)
    protocol = CPHProtocol()
    reader = Reader(transport, protocol)

    async with reader: # Използване на context manager за connect/disconnect
        logger.info("Успешно свързване!")
        
        try:
            # --- Четене на прост параметър (Мощност) ---
            logger.info("Четене на текущата мощност...")
            current_power = await reader.get_power()
            logger.info(f"Текуща мощност: {current_power} dBm")

            # --- Запис на прост параметър (Мощност) ---
            new_power = 25 # dBm
            logger.info(f"Задаване на мощност на {new_power} dBm...")
            await reader.set_power(new_power)
            logger.info("Мощността е зададена.")
            
            # Проверка чрез повторно четене
            await asyncio.sleep(0.5)
            power_after_set = await reader.get_power()
            logger.info(f"Мощност след задаване: {power_after_set} dBm")
            if power_after_set != new_power:
                logger.warning("Зададената мощност не съответства на прочетената!")
            
            # Връщане на старата мощност (пример)
            # logger.info(f"Връщане на мощността на {current_power} dBm...")
            # await reader.set_power(current_power)
            
            await asyncio.sleep(1) # Пауза

            # --- Четене на сложен параметър (ExtParams) ---
            logger.info("Четене на разширени параметри (ExtParams)...")
            ext_params = await reader.get_ext_params()
            logger.info(f"Прочетени ExtParams: {ext_params}")

            # --- Запис на сложен параметър (ExtParams) ---
            # Пример: Промяна само на relay_time
            new_ext_params = ExtParams(
                relay_mode=ext_params.relay_mode, # Запазваме старата стойност
                relay_time=5, # Нова стойност за време
                verify_flag=ext_params.verify_flag, # Запазваме старата стойност
                verify_pwd=ext_params.verify_pwd # Запазваме старата стойност
            )
            logger.info(f"Задаване на нови ExtParams: {new_ext_params}")
            await reader.set_ext_params(new_ext_params)
            logger.info("Разширените параметри са зададени.")

            # Проверка чрез повторно четене
            await asyncio.sleep(0.5)
            params_after_set = await reader.get_ext_params()
            logger.info(f"ExtParams след задаване: {params_after_set}")
            if params_after_set.relay_time != new_ext_params.relay_time:
                 logger.warning("Зададените ExtParams не съответстват на прочетените!")
            
            # Връщане на старите параметри (пример)
            # logger.info(f"Връщане на старите ExtParams...")
            # await reader.set_ext_params(ext_params)

        except CommandError as e:
            logger.error(f"Командата неуспешна със статус: {e.status_code:#04x}")
        except Exception as e:
            logger.exception(f"Възникна грешка при работа с параметри: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 