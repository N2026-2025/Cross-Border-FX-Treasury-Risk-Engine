import re
with open('interview/interview_qa.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Translate remaining English to Spanish
translations = {
    'Arbitrage detection': 'Detección de arbitraje',
    'compares two rates': 'compara dos tasas',
    'A and B': 'A y B',
    'Spread in bps': 'Spread en bps',
    '|(RateA - RateB) / RateA|': '|(RateA - RateB) / RateA|',
    '× 10,000': '× 10,000',
    'If spread exceeds threshold': 'Si el spread supera el umbral',
    '(default 50 bps)': '(umbral default 50 bps)',
    'a signal is generated': 'se genera una señal',
    'Direction:': 'Dirección:',
    'if RateA > RateB': 'si RateA > RateB',
    'BUY at B': 'COMPRAR en B',
    'SELL at A': 'VENDER en A',
    'if RateA > RateB, BUY at B, SELL at A': 'si RateA > RateB, COMPRAR en B, VENDER en A',
}

for en, es in translations.items():
    content = content.replace(en, es)

with open('interview/interview_qa.md', 'w', encoding='utf-8') as f:
    f.write(content)

print('Translation complete')