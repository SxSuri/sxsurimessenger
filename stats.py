from contextlib import contextmanager
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from util.json_type import JSONType
import settings

class Base(declarative_base()):
	__abstract__ = True

class DBClient(Base):
	__tablename__ = 't_client'
	
	id = sa.Column(sa.Integer, nullable = False, primary_key = True)
	data = sa.Column(JSONType, nullable = False)

class HourlyClientStats(Base):
	__tablename__ = 't_stats_hour_client'
	
	hour = sa.Column(sa.Integer, nullable = False, primary_key = True)
	client_id = sa.Column(sa.Integer, nullable = False, primary_key = True)
	users_active = sa.Column(sa.Integer, nullable = False, server_default = '0')
	messages_sent = sa.Column(sa.Integer, nullable = False, server_default = '0')
	messages_received = sa.Column(sa.Integer, nullable = False, server_default = '0')

class CurrentStats(Base):
	__tablename__ = 't_stats_current'
	
	key = sa.Column(sa.String, nullable = False, primary_key = True)
	date_updated = sa.Column(sa.DateTime, nullable = False)
	value = sa.Column(JSONType, nullable = False)

engine = sa.create_engine(settings.STATS_DB)
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
