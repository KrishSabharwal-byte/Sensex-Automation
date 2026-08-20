import urllib.request, json
from datetime import datetime

print("Downloading OpenAPIScripMaster.json...")
url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=45)
raw = json.loads(resp.read().decode('utf-8'))

sensex_opts = [x for x in raw if x.get('exch_seg') == 'BFO' and 'SENSEX' in x.get('name', '') and x.get('instrumenttype') == 'OPTIDX']
print(f'Found {len(sensex_opts)} BFO Sensex options')

def parse_exp(e_str):
    try:
        return datetime.strptime(e_str, '%d%b%Y')
    except:
        return datetime(2099, 1, 1)

all_exp = list(set(x.get('expiry') for x in sensex_opts if x.get('expiry')))
all_exp.sort(key=parse_exp)
current_weekly = all_exp[0] if all_exp else '20AUG2026'
print(f'Current Weekly Expiry: {current_weekly}')

sensex_weekly = [x for x in sensex_opts if x.get('expiry') == current_weekly]
print(f'Found {len(sensex_weekly)} contracts for {current_weekly}')

token_map = {}
for x in sensex_weekly:
    sym = x.get('symbol', '')
    tok = x.get('token', '')
    try:
        raw_strike = float(x.get('strike', 0))
        strike_val = int(raw_strike / 100.0) if raw_strike > 100000 else int(raw_strike)
    except:
        continue
    opt_type = 'CE' if sym.endswith('CE') else ('PE' if sym.endswith('PE') else '')
    if opt_type and strike_val:
        key = f'{strike_val}_{opt_type}'
        token_map[key] = {
            'symbol': sym,
            'token': tok,
            'strike': strike_val,
            'option_type': opt_type,
            'expiry': current_weekly
        }

print(f'Generated {len(token_map)} items in token_map')
with open('sensex_bfo_tokens.json', 'w') as f:
    json.dump(token_map, f, indent=2)

print('Saved sensex_bfo_tokens.json successfully!')
