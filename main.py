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

response = requests.post('https://api.miluma.lumapr.com/miluma-outage-api/outage/municipality/towns', headers=headers, json=json_data)

# date_utc = datetime.utcnow()
ast = pytz.timezone('America/Puerto_Rico')
date_format = '%Y-%m-%d %H.%M.%S %Z%z'

utc = pytz.utc
utc_dt = utc.localize(datetime.utcnow())
loc_dt = utc_dt.astimezone(ast)
# print(loc_dt.strftime(date_format))

path = Path(f'{loc_dt.year}/{loc_dt.month}/{loc_dt.day}/')
# path.mkdir(parents=True, exist_ok=True)

filepath = path.joinpath(f'{loc_dt.strftime(date_format)}.json')
# with open(filepath, 'w') as fd:
#     json.dump(response.json(), fd)

# Now we write it to GitHub
token = os.environ.get('ghtoken')
g = github.Github(token)
repo = g.get_repo("rubenvarela/luma-outages-data")
repo.create_file(f"{filepath}", message=f"New export created {loc_dt.strftime(date_format)}", content=json.dumps(response.json()), branch="main")
