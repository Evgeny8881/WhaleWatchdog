#!/usr/bin/env python3
import os
import time
import argparse
from dotenv import load_dotenv
from web3 import Web3

# Загрузка переменных окружения из .env
load_dotenv()
INFURA_URL = os.getenv('INFURA_URL')
if not INFURA_URL:
    print("Error: INFURA_URL not set in .env")
    exit(1)

w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# Известные DEX-роутеры
DEX_ROUTERS = {
    "UniswapV2": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
    "UniswapV3": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
    "Sushiswap": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
}

TRANSFER_EVENT_SIG = w3.keccak(text="Transfer(address,address,uint256)").hex()

def decode_transfer(log):
    from_addr = '0x' + log['topics'][1].hex()[-40:]
    to_addr   = '0x' + log['topics'][2].hex()[-40:]
    value     = int(log['data'], 16)
    return from_addr, to_addr, value

def main():
    parser = argparse.ArgumentParser(
        description="WhaleWatchdog: отслеживает крупные переводы ERC-20 на DEX-роутеры"
    )
    parser.add_argument('token', help="Адрес ERC-20 контракта")
    parser.add_argument('--threshold', type=float, default=10000.0,
                        help="Порог в токенах")
    parser.add_argument('--poll-interval', type=int, default=10,
                        help="Интервал опроса в секундах")
    parser.add_argument('--start-block', type=int, default=None,
                        help="Номер блока, с которого начать (по умолчанию — текущий)")
    args = parser.parse_args()

    # Получаем decimals токена
    abi = '[{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]'
    token = w3.eth.contract(address=w3.toChecksumAddress(args.token), abi=abi)
    decimals = token.functions.decimals().call()
    threshold_wei = int(args.threshold * 10**decimals)

    start_block = args.start_block or w3.eth.block_number
    print(f"Старт мониторинга с блока {start_block}, порог {args.threshold} токенов.")

    current = start_block
    while True:
        latest = w3.eth.block_number
        if latest >= current:
            for blk in range(current, latest + 1):
                logs = w3.eth.get_logs({
                    'fromBlock': blk,
                    'toBlock': blk,
                    'address': w3.toChecksumAddress(args.token),
                    'topics': [TRANSFER_EVENT_SIG]
                })
                for log in logs:
                    frm, to, val = decode_transfer(log)
                    if val >= threshold_wei and to in map(w3.toChecksumAddress, DEX_ROUTERS.values()):
                        human_amt = val / 10**decimals
                        dex = next(name for name, addr in DEX_ROUTERS.items()
                                   if w3.toChecksumAddress(addr) == to)
                        print(f"[Block {blk}] Whale transfer: {human_amt:.2f} tokens "
                              f"from {frm} → DEX {dex} ({to})")
            current = latest + 1
        time.sleep(args.poll_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting WhaleWatchdog.")
