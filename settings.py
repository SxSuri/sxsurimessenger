DB = 'sqlite:///../server/escargot.sqlite'
STATS_DB = 'sqlite:///../server/stats.sqlite'
DEBUG = False
PORT = 8081
CACHE_BUST_KEY = 0
# The live server DB is not up to date with the server's `master`.
# Until that's the case, the site has to use the old DB structure.
# (The live server's `USE_OLD_DB` is set to `True`.)
USE_OLD_DB = True

# Set this in settings_local to use reCAPTCHA
RECAPTCHA = {
	'api_key': None,
	'secret_key': None,
}

# Set this in `settings_local` to use SendGrid
SENDGRID_API_KEY = None

try:
	from settings_local import *
except ImportError:
	raise Exception("Please create settings_local.py")
