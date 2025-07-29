import os

DATA_PATH = os.path.join(os.path.dirname(__file__), 'common-passwords.txt')

with open(DATA_PATH, 'r', encoding='utf-8') as f:
    COMMON_PASSWORDS = { line.strip() for line in f if line.strip() }
