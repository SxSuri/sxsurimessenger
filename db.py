from typing import Any
import json
from contextlib import contextmanager
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from util import hash
from util.json_type import JSONType
import settings
from settings import USE_OLD_DB

class Base(declarative_base()):
	__abstract__ = True

class User(Base):
	__tablename__ = 't_user'
	
	id = sa.Column(sa.Integer, nullable = False, primary_key = True)
	date_created = sa.Column(sa.DateTime, nullable = True, default = datetime.utcnow)
	date_login = sa.Column(sa.DateTime, nullable = True)
	uuid = sa.Column(sa.String, nullable = False, unique = True)
	email = sa.Column(sa.String, nullable = False, unique = True)
	verified = sa.Column(sa.Boolean, nullable = False)
	name = sa.Column(sa.String, nullable = False)
	message = sa.Column(sa.String, nullable = False)
	password = sa.Column(sa.String, nullable = False)
	settings = sa.Column(JSONType, nullable = False)
	groups = sa.Column(JSONType, nullable = False)
	contacts = sa.Column(JSONType, nullable = False)
	
	# Can't use `settings.USE_OLD_DB` because in this scope, `settings`
	# is the field... wah wah wahhhhhh.
	if USE_OLD_DB:
		type = sa.Column(sa.Integer, nullable = False, default = 1)
		password_md5 = sa.Column(sa.String, nullable = False)
	else:
		# Data specific to front-ends; e.g. different types of password hashes
		# E.g. front_data = { 'msn': { ... }, 'ymsg': { ... }, ... }
		_front_data = sa.Column(JSONType, name = 'front_data', nullable = False, default = {})
	
	__table_args__ = (sa.Index('email_ci_index', sa.text('LOWER(email)'), unique = True),)
	
	def set_front_data(self, frontend: str, key: str, value: Any) -> None:
		fd = self._front_data or {}
		if frontend not in fd:
			fd[frontend] = {}
		fd[frontend][key] = value
		# As a side-effect, this also makes `._front_data` into a new object,
		# so SQLAlchemy picks up the fact that it's been changed.
		# (SQLAlchemy only does shallow comparisons on fields by default.)
		self._front_data = _simplify_json_data(fd)
	
	def get_front_data(self, frontend: str, key: str) -> Any:
		fd = self._front_data
		if not fd: return None
		fd = fd.get(frontend)
		if not fd: return None
		return fd.get(key)

def _simplify_json_data(data: Any) -> Any:
	if isinstance(data, dict):
		d = {}
		for k, v in data.items():
			v = _simplify_json_data(v)
			if v is not None:
				d[k] = v
		if not d:
			return None
		return d
	if isinstance(data, (list, tuple)):
		return [_simplify_json_data(x) for x in data]
	return data

engine = sa.create_engine(settings.DB)
session_factory = sessionmaker(bind = engine)

@contextmanager
def Session():
	if Session._depth > 0:
		yield Session._global
		return
	session = session_factory()
	Session._global = session
	Session._depth += 1
	try:
		yield session
		session.commit()
	except:
		session.rollback()
		raise
	finally:
		session.close()
		Session._global = None
		Session._depth -= 1
Session._global = None
Session._depth = 0
