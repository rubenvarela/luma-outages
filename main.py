import requests
import json
from datetime import datetime
import pytz
from pathlib import Path
import github #pygithub
import os

with open('towns.json') as fd:
    towns = json.load(fd)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:104.0) Gecko/20100101 Firefox/104.0',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.5',
    # 'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://miluma.lumapr.com/',
    # Already added when you pass json=
    # 'Content-Type': 'application/json',
    'Origin': 'https://miluma.lumapr.com',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
}

json_data = towns

response_towns = requests.post('https://api.miluma.lumapr.com/miluma-outage-api/outage/municipality/towns', headers=headers, json=json_data)
response_clients = requests.get('https://api.miluma.lumapr.com/miluma-outage-api/outage/regionsWithoutService')
# date_utc = datetime.utcnow()
ast = pytz.timezone('America/Puerto_Rico')
date_format = '%Y-%m-%d %H.%M.%S %Z%z'

utc = pytz.utc
utc_dt = utc.localize(datetime.utcnow())
loc_dt = utc_dt.astimezone(ast)
# print(loc_dt.strftime(date_format))

path = Path(f'{loc_dt.year}/{loc_dt.month}/{loc_dt.day}/')
filepath_towns = path.joinpath(f'{loc_dt.strftime(date_format)}.json')
filepath_clients = path.joinpath(f'{loc_dt.strftime(date_format)}--clients.json')

# If we aren't running in GitHub, we save to disk too
if not os.environ.get('GITHUB_ACTIONS') and os.environ.get('save_to_disk') == '1':
    path.mkdir(parents=True, exist_ok=True)

    with open(filepath_towns, 'w') as fd:
        json.dump(response_towns.json(), fd)

    with open(filepath_clients, 'w') as fd:
        json.dump(response_clients.json(), fd)

if os.environ.get('save_to_github') == '1':
    # Now we write it to GitHub
    token = os.environ.get('ghtoken')
    if not token:
        if Path('env').exists():
            with open('env') as fd:
                token = fd.readline().split('=')[1][1:-2] # split on =, remove quotes with slicing
    g = github.Github(token)
    repo = g.get_repo("rubenvarela/luma-outages-data")
    repo.create_file(f"{filepath_towns}", message=f"New export created {loc_dt.strftime(date_format)} Towns", content=json.dumps(response_towns.json()), branch="main")
    repo.create_file(f"{filepath_clients}", message=f"New export created {loc_dt.strftime(date_format)} Clients", content=json.dumps(response_clients.json()), branch="main")
