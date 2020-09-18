# Escargot Site

This repo contains code for https://escargot.log1p.xyz.

## Running locally

Since the site depends on databases from the [msn-server](https://gitlab.com/valtron/msn-server) project,
it's recommended you should have a folder structure like this:
- `escargot/site` (containing this repository)
- `escargot/server` (containing [msn-server](https://gitlab.com/valtron/msn-server))

Then do the following steps:
- Make sure you `$PYTHONPATH` (`%PYTHONPATH%` on Windows) contains `.`. (This is so you run python scripts from subdirectories, e.g. `python cmd/resetpw.py`.)
- Create `settings_local.py` (if you don't, you'll get an error telling you to anyway). Inside, for starters, you need to define:
    - `DEBUG = True` so the development server serves static files (images, etc.)
    - `DB` and `STATS_DB` need to point to the database files. To create them:
        - Go in `escargot/server`
        - (You should be using the `dev` branch: `git checkout dev`)
        - Run `python script/dbcreate.py` to create `{escargot,stats}.sqlite`
        - Inside `escargot/site/settings_local.py`, set:
            - `DB = 'sqlite:///../server/escargot.sqlite'`
            - `STATS_DB = 'sqlite:///../server/stats.sqlite'`
