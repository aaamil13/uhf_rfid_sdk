from setuptools import setup, find_packages
    name="uhf_rfid",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyserial-asyncio",
        "asyncio",
    ],
    entry_points={
        "console_scripts": []
    }
)
