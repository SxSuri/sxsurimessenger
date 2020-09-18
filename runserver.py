from aiohttp import web
from ctrl_site import create_app

import settings

def main():
	app = create_app(serve_static = settings.DEBUG)
	web.run_app(app, port = settings.PORT)

if __name__ == '__main__':
	main()
