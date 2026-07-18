import requests
import json
from datetime import datetime, timedelta, UTC
from zoneinfo import ZoneInfo
from pathlib import Path
import github #pygithub
import os
from dotenv import load_dotenv

# Fill in ghtoken from a local `env` file if it's not already set in the
# environment (e.g. by GitHub Actions).
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
hour_format = '%Y-%m-%d %H.'
date_format = hour_format + '%M.%S %Z%z'
CLIENTS_SUFFIX = '--clients.json'

loc_dt = datetime.now(UTC).astimezone(ast)


def _day_path(dt):
    return f'{dt.year}/{dt.month}/{dt.day}'


path = Path(_day_path(loc_dt))
filepath_towns = path.joinpath(f'{loc_dt.strftime(date_format)}.json')
filepath_clients = path.joinpath(f'{loc_dt.strftime(date_format)}--clients.json')

towns_data = response_towns.json()
clients_data = response_clients.json()

path.mkdir(parents=True, exist_ok=True)

with open(filepath_towns, 'w') as fd:
    json.dump(towns_data, fd)

with open(filepath_clients, 'w') as fd:
    json.dump(clients_data, fd)


def _day_files(repo, dt, kind):
    """List this day's files of one type ('towns' or 'clients'), oldest to newest."""
    try:
        contents = repo.get_contents(_day_path(dt))
    except github.UnknownObjectException:
        return []
    if kind == 'towns':
        matches = [c for c in contents if c.name.endswith('.json') and not c.name.endswith(CLIENTS_SUFFIX)]
    else:
        matches = [c for c in contents if c.name.endswith(CLIENTS_SUFFIX)]
    return sorted(matches, key=lambda c: c.name)


def _last_or_none(files):
    return files[-1] if files else None


def _check_type(repo, loc_dt, kind, new_data):
    """Compare new_data against the latest snapshot of this type, and check
    whether the current hour already has an entry of this type."""
    today_files = _day_files(repo, loc_dt, kind)
    has_entry_this_hour = any(c.name.startswith(loc_dt.strftime(hour_format)) for c in today_files)

    latest_file = _last_or_none(today_files)
    if latest_file is None:
        latest_file = _last_or_none(_day_files(repo, loc_dt - timedelta(days=1), kind))

    unchanged = latest_file is not None and json.loads(latest_file.decoded_content) == new_data
    return unchanged, has_entry_this_hour


def _should_write(repo, loc_dt, towns_data, clients_data):
    """Towns and clients are written together as a pair. If either is
    missing a snapshot for the current hour, or either has changed, write
    both. Only skip when both are already covered for this hour and both
    are unchanged."""
    towns_unchanged, towns_has_hour = _check_type(repo, loc_dt, 'towns', towns_data)
    if not towns_unchanged:
        # Already know we must write and it isn't a heartbeat - no need to check clients.
        return True, False

    clients_unchanged, clients_has_hour = _check_type(repo, loc_dt, 'clients', clients_data)
    both_unchanged = towns_unchanged and clients_unchanged
    both_have_hour = towns_has_hour and clients_has_hour
    return not (both_unchanged and both_have_hour), both_unchanged


token = os.environ.get('ghtoken')
if token:
    # Having a token is the signal to push - no separate on/off switch needed.
    g = github.Github(token, lazy=True)
    repo = g.get_repo("rubenvarela/luma-outages-data")

    write, heartbeat = _should_write(repo, loc_dt, towns_data, clients_data)
    if write:
        suffix = ' (unchanged, hourly heartbeat)' if heartbeat else ''
        for filepath, label, data in (
            (filepath_towns, 'Towns', towns_data),
            (filepath_clients, 'Clients', clients_data),
        ):
            repo.create_file(
                f"{filepath}",
                message=f"New export created {loc_dt.strftime(date_format)} {label}{suffix}",
                content=json.dumps(data),
                branch="main",
            )
