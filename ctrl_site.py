import re
import jinja2
from aiohttp import web
from functools import lru_cache
from markupsafe import Markup
import asyncio
import lxml
import struct
import binascii
from sqlalchemy import func

from db import Session, User
from util import hash
from util.auth import AuthService
from util.misc import gen_uuid
import settings

def create_app(*, serve_static = False):
	app = App()
	
	app.router.add_get('/', page_index)
	app.router.add_get('/stats', page_stats)
	app.router.add_get('/forgot', page_forgot)
	app.router.add_post('/forgot', page_forgot)
	app.router.add_get('/reset/{token}', page_reset)
	app.router.add_post('/reset/{token}', page_reset)
	app.router.add_get('/etc/MsgrConfig', page_msgr_config)
	app.router.add_post('/etc/MsgrConfig', page_msgr_config)
	app.router.add_get('/news', page_news)
	app.router.add_get('/etc/SxSuri Messenger-today', lambda req: page_news(req, tab = True))
	app.router.add_get('/status', page_status)
	app.router.add_get('/wlm-puid', page_wlm_puid)
	app.router.add_post('/wlm-puid', page_wlm_puid)
	app.router.add_get('/faq', page_faq)
	app.router.add_get('/downloads', page_downloads)
	app.router.add_get('/register', page_register)
	app.router.add_post('/register', page_register)
	app.router.add_get('/patching', page_patching)
	if serve_static:
		app.router.add_static('/static', 'static')
	app.router.add_route('*', '/{path:.*}', handle_404)
	app.jinja_env = jinja2.Environment(
		loader = jinja2.FileSystemLoader('tmpl'),
		autoescape = jinja2.select_autoescape(default = False),
	)
	return app

class App(web.Application):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.stats = None
		self.server_status = None
		self.auth_service = AuthService()
	
	async def startup(self):
		self.loop.create_task(self.sync_service_status())
		self.loop.create_task(self.sync_stats())
	
	async def sync_service_status(self):
		import time
		from datetime import datetime
		
		while True:
			recv_time = 0
			send_time = 0
			difference_time = 0
			protocol = None
			status = None
			
			try:
				_, protocol = await self.loop.create_connection(MSNPTest, 'm1.sxsurimessenger.ml', 1863)
				send_time = protocol.send_time
				
				while protocol.buffer.find(b'\r\n') == -1 and not protocol.transport.is_closing():
					recv_time = time.time()
					difference_time = recv_time - protocol.send_time
					if difference_time >= 10: break
					await asyncio.sleep(0.1)
				if protocol.transport.is_closing():
					status = 'down'
				else:
					if difference_time >= 10:
						status = 'slow'
					else:
						status = 'ok'
					protocol.transport.close()
			except asyncio.CancelledError:
				raise
			except:
				if protocol is None:
					status = 'down'
			
			self.server_status = {
				'status': status,
				'last_updated': datetime.utcnow(),
			}
			
			await asyncio.sleep(120)
	
	async def sync_stats(self):
		from datetime import datetime, timedelta
		from itertools import groupby
		import stats
		
		while True:
			now = datetime.utcnow()
			five_minutes_ago = now - timedelta(minutes = 5)
			hour_cutoff = now.timestamp() // 3600 - 24
			with stats.Session() as sess:
				stat = sess.query(stats.CurrentStats).filter(
					stats.CurrentStats.key == 'logged_in',
					stats.CurrentStats.date_updated > five_minutes_ago
				).one_or_none()
				logged_in = getattr(stat, 'value', 0)
				clients_by_id = {
					row.id: row.data
					for row in sess.query(stats.DBClient).all()
				}
				by_hour = sorted([
					{
						'hour': hcs.hour,
						'hour_formatted': _format_hour(hcs.hour),
						'client_formatted': _format_client(clients_by_id.get(hcs.client_id)),
						'users_active': int(hcs.users_active),
						'messages_sent': hcs.messages_sent,
						'messages_received': hcs.messages_received,
					}
					for hcs in sess.query(stats.HourlyClientStats).filter(stats.HourlyClientStats.hour >= hour_cutoff).all()
				], key = lambda x: (-x['hour'], -x['users_active']))
				by_hour = [
					(hour_formatted, list(l))
					for hour_formatted, l in groupby(by_hour, lambda x: x['hour_formatted'])
				]
			self.stats = {
				'logged_in': logged_in,
				'by_hour': by_hour,
			}
			await asyncio.sleep(300)

class MSNPTest(asyncio.Protocol):
	def __init__(self):
		self.transport = None
		self.buffer = b''
		self.send_time = 0
	
	def connection_made(self, transport):
		import time
		
		self.transport = transport
		self.transport.write(b'VER 1 MSNP15\r\n')
		self.send_time = time.time()
	
	def connection_lost(self, exc):
		self.buffer = b''
		self.transport = None
	
	def data_received(self, data):
		if self.buffer:
			self.buffer += data
		else:
			self.buffer = data

def _format_hour(hour):
	from datetime import datetime
	dt = datetime.fromtimestamp(hour * 3600)
	return dt.strftime("%Y-%m-%d, %H:00 - %H:59 UTC")

def _format_client(client):
	if client is None:
		return "(Unknown)"
	p = client['program']
	v = client['version']
	if p == 'msn':
		if v.startswith('MSNP') and client['via'] != 'webtv':
			v = _guess_msn_version(int(v[4:]))
		# Rely on custom/MSNP version string for WebTV clients until we find a reliable way to detect WebTV client builds
		if client['via'] == 'webtv':
			v = 'WebTV Client ({})'.format(v)
	s = "{} {}".format(p.upper(), v)
	if client['via'] not in ('direct', 'webtv'):
		s += ", {}".format(client['via'].upper())
	return s

def _guess_msn_version(dialect):
	if dialect <= 2:
		return "1.?"
	if dialect <= 4:
		return "2.?"
	if dialect <= 5:
		return "3.?"
	if dialect <= 7:
		return "4.?"
	return "?/MSNP" + str(dialect)

async def page_stats(req):
	return render(req, 'stats.html', { 'stats': req.app.stats })

async def page_status(req):
	return render(req, 'status.html', { 'server_status': req.app.server_status })

async def page_index(req):
	return render(req, 'index.html')

async def page_register(req):
	errors = None
	email = None
	created_email = None
	support_old = None
	if req.method == 'POST':
		data = await req.post()
		
		valid_recaptcha = await check_recaptcha(req, data.get('g-recaptcha-response') or '')
		if not valid_recaptcha:
			errors = { 'recaptcha': "Invisible reCAPTCHA failed." }
		
		if not errors:
			email = data.get('email') or ''
			pw1 = data.get('password1') or ''
			pw2 = data.get('password2') or ''
			support_old = (data.get('support_old') == 'true')
			errors = create_user(email, pw1, pw2, support_old)
		
		if not errors:
			return web.HTTPFound('/register?created_email={}'.format(email))
	else:
		created_email = req.query.get('created_email')
	
	return render(req, 'register.html', {
		'errors': errors,
		'email': email,
		'support_old': support_old,
		'created_email': created_email,
		'recaptcha_api_key': settings.RECAPTCHA['api_key'],
	})

async def page_wlm_puid(req):
	errors = None
	email = None
	puid = None
	
	if req.method == 'POST':
		data = await req.post()
		email = data.get('email') or ''
		password = data.get('password') or ''
		
		if not email or not password:
			errors = {'email': "Email or password was not specified."}
		
		if not errors:
			with Session() as sess:
				user = _get_user(email)
				if user is None:
					errors = {'email': EMAIL_INVALID_ACCOUNT}
				if not errors:
					if not hash.hasher.verify(password, user.password):
						errors = {'email': EMAIL_INVALID_ACCOUNT}
					if not errors:
						try:
							puid = _puid_format(user.uuid)
						except:
							errors = {'puid': "An internal error occurred while generating your PUID. Try again."}
		
		if errors and 'puid' not in errors:
			errors['puid'] = "Your PUID could not be generated. See errors below."
	
	return render(req, 'wlm-puid.html', {
		'errors': errors,
		'email': email,
		'puid': puid,
	})

async def handle_404(req):
	return render(req, '404.html', status = 404)

async def check_recaptcha(req, recaptcha_response):
	if not settings.RECAPTCHA['secret_key']:
		return True
	
	import aiohttp
	async with aiohttp.ClientSession() as session:
		req = session.post('https://www.google.com/recaptcha/api/siteverify', json = {
			'secret': settings.RECAPTCHA['secret_key'],
			'response': recaptcha_response,
			'remoteip': req.remote,
		})
		async with req as resp:
			resp = await resp.json()
	return resp['success']

async def page_msgr_config(req):
	action = None
	ver = None
	
	if req.method == 'POST':
		action = await _preprocess_soap(req)
		if action is None:
			return web.Response(status = 500, text = '')
		action_str = _get_tag_localname(action)
	elif req.method == 'GET':
		action_str = req.query.get('op')
		ver = req.query.get('ver')
	
	# Can't properly check for action string on GET requests because current WLM 8 patches screw with the `op` query parameter (`?padding=qqqqq?op=GetClientConfig&...`)
	if req.method == 'POST' and action_str != 'GetClientConfig':
		return web.Response(status = 500, text = '')
	
	msgr_config = _get_msgr_config(req, action, ver)
	if req.method == 'POST':
		with open('MsgrConfig.msn.envelope.xml') as fh:
			envelope = fh.read()
		msgr_config = envelope.format(MsgrConfig = msgr_config)
	return web.HTTPOk(content_type = 'text/xml', text = msgr_config)

async def _preprocess_soap(req):
	from lxml.etree import fromstring as parse_xml
	
	body = await req.read()
	root = parse_xml(body)
	
	action = _find_element(root, 'Body/*[1]')
	
	return action

def _find_element(xml, query):
	thing = xml.find('{*}' + query.replace('/', '/{*}'))
	return thing

def _get_tag_localname(elm):
	return lxml.etree.QName(elm.tag).localname

def _get_msgr_config(req, action, ver):
	query = req.query
	result = None
	
	if req.method == 'GET':
		# Since v8 only does GET requests to MsgrConfig, version checking shouldn't be a concern right now (that'll be added for WLM 2009)
		with open('MsgrConfig.wlm.8.xml') as fh:
			config = fh.read()
		with open('MsgrConfig.tabs.xml') as fh:
			config_tabs = fh.read()
		result = config.format(
			tabs = config_tabs,
		)
	elif req.method == 'POST':
		with open('MsgrConfig.msn.xml') as fh:
			config = fh.read()
		with open('MsgrConfig.tabs.xml') as fh:
			config_tabs = fh.read()
		result = config.format(
			tabs = config_tabs,
		)
	
	return result or ''

async def page_news(req, *, tab = False):
	return render(req, 'news.html', { 'from_tab': tab })

async def page_forgot(req):
	errors = None
	email = None
	sent_to = None
	if req.method == 'POST':
		data = await req.post()
		email = data.get('email') or ''
		errors = send_password_reset(email, req.app.auth_service)
		if not errors:
			return web.HTTPFound('/forgot?sent_to={}'.format(email))
	else:
		sent_to = req.query.get('sent_to')
	
	return render(req, 'forgot.html', {
		'errors': errors,
		'email': email,
		'sent_to': sent_to,
	})

async def page_reset(req):
	auth_service = req.app.auth_service
	
	token = req.match_info.get('token', '')
	email = auth_service.get_token(PURPOSE_PWRESET, token)
	valid_token = (email is not None)
	errors = None
	reset_success = False
	support_old = None
	
	if valid_token:
		if req.method == 'POST':
			data = await req.post()
			pw1 = data.get('password1') or ''
			pw2 = data.get('password2') or ''
			support_old = (data.get('support_old') == 'true')
			errors = change_password(email, pw1, pw2, support_old)
			if not errors:
				auth_service.pop_token(PURPOSE_PWRESET, token)
				reset_success = True
		else:
			with Session() as sess:
				user = _get_user(email)
				if user:
					if settings.USE_OLD_DB:
						support_old = bool(user.password_md5)
					else:
						support_old = user.get_front_data('msn', 'pw_md5')
	
	return render(req, 'reset.html', {
		'valid_token': valid_token,
		'errors': errors,
		'reset_success': reset_success,
		'support_old': support_old,
	})

async def page_faq(req):
	return render(req, 'faq.html')

async def page_downloads(req):
	return render(req, 'downloads.html')

async def page_patching(req):
	return render(req, 'patching.html')

def create_user(email, pw1, pw2, support_old):
	errors = {}
	_check_email(errors, email)
	_check_passwords(errors, pw1, pw2)
	if errors: return errors
	
	with Session() as sess:
		user = _get_user(email)
		if user is not None:
			errors['email'] = "Email already in use."
			return errors
		user = User(
			uuid = gen_uuid(), email = email, verified = False,
			name = email, message = '',
			settings = {}, groups = {}, contacts = {},
		)
		_set_passwords(user, pw1, support_old)
		sess.add(user)
	
	return errors

def send_password_reset(email, auth_service):
	errors = {}
	_check_email(errors, email)
	if errors: return errors
	
	with Session() as sess:
		user = _get_user(email)
		if user is None:
			errors['email'] = Markup("Email not registered with SxSuri Messenger. Did you <a href=\"/register\">sign up?</a>")
			return errors
		token = auth_service.create_token(PURPOSE_PWRESET, email, lifetime = 3600)
		sent = _send_password_reset_email(email, token)
		if not sent:
			auth_service.pop_token(PURPOSE_PWRESET, token)
			errors['email'] = "Email could not be sent."
	
	return errors

def change_password(email, pw1, pw2, support_old):
	errors = {}
	_check_passwords(errors, pw1, pw2)
	if errors: return errors
	
	with Session() as sess:
		user = _get_user(email)
		_set_passwords(user, pw1, support_old)
		user.verified = True
		sess.add(user)
	
	return errors

def _set_passwords(user, pw, support_old):
	user.password = hash.hasher.encode(pw)
	
	if support_old:
		pw_md5 = hash.hasher_md5.encode(pw)
	else:
		pw_md5 = None
	
	if settings.USE_OLD_DB:
		user.password_md5 = (pw_md5 or '')
	else:
		user.set_front_data('msn', 'pw_md5', pw_md5)

def _uuid_to_high_low(u):
	import uuid
	u = uuid.UUID(u)
	high = u.time_low % (1<<32)
	low = u.node % (1<<32)
	return (high, low)

def _puid_format(u):
	high, low = _uuid_to_high_low(u)
	n = (high * (2 ** 32)) + low
	return binascii.hexlify(struct.pack('>Q', n)).decode('utf-8').upper()

def _send_password_reset_email(email, token):
	if settings.DEBUG:
		print("""********
Password reset requested for {}.
Here is your token:

\t{}

********""".format(email, token))
		return True
	
	import sendgrid
	from sendgrid.helpers.mail import Mail, From
	
	message = Mail(
		from_email = From('no-reply@sxsurimessenger.ml', "SxSuri Messenger"),
		to_emails = email,
		subject = "SxSuri Messenger password reset requested",
		html_content = RESET_TEMPLATE.format(email = email, token = token),
	)
	try:
		sg = sendgrid.SendGridAPIClient(settings.SENDGRID_API_KEY)
		ret = sg.send(message)
	except:
		return False
	return 200 <= ret.status_code < 300

RESET_TEMPLATE = """
A password reset was requested for the SxSuri Messenger (http://sxsurimessenger.ml) account associated with {email}.

To change your password, follow this link within the next 60 minutes:

http://sxsurimessenger.ml{token}

If you did not request a password reset, ignore this email.
""".strip()

def _get_user(email):
	with Session() as sess:
		return sess.query(User).filter(func.lower(User.email) == email.lower()).one_or_none()

def _check_email(errors, email):
	if not (6 <= len(email) < 60) or ('@' not in email):
		errors['email'] = "Invalid email."
	# This check isn't relevant anymore; comment out
	#if '|' in email:
	#	# "Don't put your password in the email here; that's only when you log in to MSN < 5 or 7.5"
	#	errors['email'] = 'pass-in-email'

def _check_passwords(errors, pw1, pw2):
	if len(pw1) < 6:
		errors['password1'] = "Password too short: 6 characters minimum."
	elif pw1 != pw2:
		errors['password2'] = "Passwords don't match."

def render(req, tmpl, ctxt = None, status = 200):
	tmpl = req.app.jinja_env.get_template(tmpl)
	if ctxt is None:
		ctxt = {}
	ctxt['stats'] = req.app.stats
	ctxt['cache_buster'] = '_version={}'.format(settings.CACHE_BUST_KEY)
	content = tmpl.render(**ctxt)
	return web.Response(status = status, content_type = 'text/html', text = content)

PURPOSE_PWRESET = 'pwreset'
EMAIL_INVALID_ACCOUNT = "Email does not exist or the password given was incorrect."
