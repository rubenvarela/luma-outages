import requests
import json
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo
from pathlib import Path
import github #pygithub
import os
from dotenv import load_dotenv

# Fill in any of ghtoken/save_to_disk/save_to_github not already set in the
# environment (e.g. by GitHub Actions) from a local `env` file, if present.
load_dotenv('env')

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
ast = ZoneInfo('America/Puerto_Rico')
date_format = '%Y-%m-%d %H.%M.%S %Z%z'

loc_dt = datetime.now(UTC).astimezone(ast)

path = Path(f'{loc_dt.year}/{loc_dt.month}/{loc_dt.day}/')
filepath_towns = path.joinpath(f'{loc_dt.strftime(date_format)}.json')
filepath_clients = path.joinpath(f'{loc_dt.strftime(date_format)}--clients.json')

towns_data = response_towns.json()
clients_data = response_clients.json()

# If we aren't running in GitHub, we save to disk too
if not os.environ.get('GITHUB_ACTIONS') and os.environ.get('save_to_disk') == '1':
    path.mkdir(parents=True, exist_ok=True)

    with open(filepath_towns, 'w') as fd:
        json.dump(towns_data, fd)

    with open(filepath_clients, 'w') as fd:
        json.dump(clients_data, fd)


def _day_files(repo, dt, is_towns):
    """List this day's files of one type (towns or clients), oldest to newest."""
    try:
        contents = repo.get_contents(f'{dt.year}/{dt.month}/{dt.day}')
    except github.UnknownObjectException:
        return []
    if is_towns:
        matches = [c for c in contents if c.name.endswith('.json') and not c.name.endswith('--clients.json')]
    else:
        matches = [c for c in contents if c.name.endswith('--clients.json')]
    return sorted(matches, key=lambda c: c.name)


def _check_type(repo, loc_dt, is_towns, new_data):
    """Compare new_data against the latest snapshot of this type, and check
    whether the current hour already has an entry of this type."""
    today_files = _day_files(repo, loc_dt, is_towns)
    has_entry_this_hour = any(c.name.startswith(loc_dt.strftime('%Y-%m-%d %H.')) for c in today_files)

    latest_file = today_files[-1] if today_files else None
    if latest_file is None:
        yesterday_files = _day_files(repo, loc_dt - timedelta(days=1), is_towns)
        latest_file = yesterday_files[-1] if yesterday_files else None

    unchanged = latest_file is not None and json.loads(latest_file.decoded_content) == new_data
    return unchanged, has_entry_this_hour


def _should_write(repo, loc_dt, towns_data, clients_data):
    """Towns and clients are written together as a pair. If either is
    missing a snapshot for the current hour, or either has changed, write
    both. Only skip when both are already covered for this hour and both
    are unchanged."""
    towns_unchanged, towns_has_hour = _check_type(repo, loc_dt, True, towns_data)
    clients_unchanged, clients_has_hour = _check_type(repo, loc_dt, False, clients_data)

    if towns_unchanged and clients_unchanged and towns_has_hour and clients_has_hour:
        return False, True
    return True, (towns_unchanged and clients_unchanged)


if os.environ.get('save_to_github') == '1':
    # Now we write it to GitHub
    g = github.Github(os.environ.get('ghtoken'))
    repo = g.get_repo("rubenvarela/luma-outages-data")

    write, heartbeat = _should_write(repo, loc_dt, towns_data, clients_data)
    if write:
        suffix = ' (unchanged, hourly heartbeat)' if heartbeat else ''
        repo.create_file(f"{filepath_towns}", message=f"New export created {loc_dt.strftime(date_format)} Towns{suffix}", content=json.dumps(towns_data), branch="main")
        repo.create_file(f"{filepath_clients}", message=f"New export created {loc_dt.strftime(date_format)} Clients{suffix}", content=json.dumps(clients_data), branch="main")
