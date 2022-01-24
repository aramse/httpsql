#!/usr/bin/python -u

import os
import web
import json
import psycopg2
import sys
import prometheus_client
import time
import abc
import traceback
import jsonschema

if os.environ.get('DB_PROVIDER', None) == 'cassandra':
  from cassandra.cluster import Cluster
  from cassandra.auth import PlainTextAuthProvider

CHECK_ALIVE_PATH = '/check/alive'
CHECK_READY_PATH = '/check/ready'


# Instrumentation for monitoring
def before_request():
  web.start_time = time.time()


def after_request():
  params = web.ctx
  if params.path not in (CHECK_ALIVE_PATH, CHECK_READY_PATH):
    latency = time.time() - web.start_time
    REQUEST_COUNT.labels(params.method, params.path, params.status).inc()
    REQUEST_LATENCY.labels(params.method, params.path).observe(latency)


# General functions
def log(msg, prefix=None):
  pre = prefix + ': ' if prefix else ''
  print pre + msg


def info(msg):
  log(msg, 'INFO')


def error(msg):
  log(msg, 'ERROR')


def debug(msg):
  if DEBUG:
    log(msg, 'DEBUG')


def fatal(msg):
  log(msg, 'FATAL')
  sys.exit(1)


def check_no_op(web_obj):
  return web_obj.input(no_op=False).no_op


# Generic Database class
class Database(object):
  __metaclass__ = abc.ABCMeta

  FIELD_MAPPING = {
    'string': 'varchar(64)',
    'int': 'int',
    'boolean': 'boolean'
  }

  SPECIAL_QUERY_PARAMS = ['no_op']

  PROVIDER = None
  DEFAULT_PORT = None

  def __init__(self, host, port=DEFAULT_PORT, user=None, pword=None):
    self.host = host
    self.port = port
    self.user = user
    self.pword = pword
    self.connection = None  # this connection is created with the connect() method

  def __str__(self):
    return json.dumps({
      'resource': 'database',
      'provider': self.PROVIDER,
      'host': self.host,
      'port': self.port,
      'user': self.user,
      'pword': self.pword
    })

  def connect(self):
    info('connecting to ' + str(self))
    try:
      self.connection = self.get_connection()
      return True
    except Exception as e:
      error('unable to connect: ' + str(e))
      return False

  def query(self, query, read=False):
    debug('querying: ' + str(self))
    debug('with sql: ' + query)
    return self.exec_query(query, read=read)

  def check_health(self):
    debug('checking health for ' + str(self))
    try:
      self.check_connectivity()
      return True
    except Exception as e:
      error('health check failed: ' + str(e))
      return False

  def initialize(self):
    return True

  def get_cmd_create_table(self, table_name, request_obj):
    # validate with schema
    debug('validating ' + json.dumps(request_obj) + ' against schema')
    schema = {
      "$schema": "http://json-schema.org/draft-04/schema#",
      "required": ["fields"],
      "additionalProperties": False,
      "properties": {
        "fields": {
          "patternProperties": {
            "^.*$": {"type": "string", "enum": self.FIELD_MAPPING.keys()}
          }
        },
        "key": {"type": "string"}
      }
    }
    try:
      jsonschema.validate(request_obj, schema)
    except jsonschema.exceptions.ValidationError as e:
      traceback.print_exc()
      error('failed schema validation: ' + str(e))
      return web.badrequest(message=str(e))
    # mock example for shirts table: {"key": "name", "fields": {"name": "string", "price": "int", "size": "string"}}
    sql = 'CREATE TABLE ' + table_name + ' ('
    sql += ', '.join([ field + ' ' + self.FIELD_MAPPING[data_type] + (' PRIMARY KEY' if field == request_obj.get('key', None) else '') for field, data_type in request_obj['fields'].items()])
    sql += ')'
    return sql

  def get_cmd_delete_table(self, table_name):
    return 'DROP TABLE ' + table_name

  def get_cmd_get_data(self, table_name):
    sql = 'SELECT * FROM ' + table_name
    params = {k:v for k,v in web.input().items() if k not in self.SPECIAL_QUERY_PARAMS}
    if len(params):
        sql += ' WHERE ' + ' AND '.join([k + ' = ' + ("'" + v + "'" if isinstance(v, str) else v) for k,v in params.items()])
    return sql

  def get_cmd_insert_data(self, table_name, request_obj):
    # mock: [{"name": "t-shirt", "price": 10, "size": "M"}]
    sql = ''
    for row in request_obj:
      sql += 'INSERT INTO ' + table_name + \
             '(' + ','.join(row.keys()) + ') ' + \
             'VALUES (' + ','.join(
        ["'" + v + "'" if isinstance(v, basestring) else str(v) for v in row.values()]) + '); '
    return sql

  def get_cmd_delete_data(self, table_name, fName, fValue):
    return 'DELETE FROM ' + table_name + ' WHERE ' + fName + '=' + fValue


  @abc.abstractmethod
  def get_connection(self):
    return

  @abc.abstractmethod
  def exec_query(self, query, read=False):
    return

  @abc.abstractmethod
  def check_connectivity(self):
    return

  @staticmethod
  def get_db_class(provider):
    for cl in Database.__subclasses__():
      if cl.PROVIDER == provider:
        return cl
    return None


# Supported Database classes
class PostgresDB(Database):
  PROVIDER = 'postgres'
  DEFAULT_PORT = 5432

  def __init__(self, host, port=DEFAULT_PORT, user='postgres', pword='postgres'):
    Database.__init__(self, host, port, user, pword)

  def get_connection(self):
    conn = psycopg2.connect(host=self.host, user=self.user, password=self.pword)
    conn.autocommit = True
    return conn

  def exec_query(self, query, read=False):
    cur = self.connection.cursor()
    try:
      cur.execute(query)
    except Exception as e:
      traceback.print_exc()
      if read:
        return web.badrequest(message=str(e))
      else:
        return False
    if read:
      res = []
      fields = [desc[0] for desc in cur.description]
      rows = cur.fetchall()
      for row in rows:
        obj = {}
        for i in range(len(fields)):
          obj[fields[i]] = row[i]
        res.append(obj)
      res = json.dumps(res)
      # debug('result:')
      # debug(res)
      return res
    else:
      return True

  def check_connectivity(self):
    self.query('SELECT NULL')


class CassandraDB(Database):
  PROVIDER = 'cassandra'
  DEFAULT_PORT = 9042
  KEYSPACE = 'httpsql'

  FIELD_MAPPING = {
    'string': 'text',
    'int': 'int',
    'boolean': 'boolean'
  }

  def __init__(self, host, port=DEFAULT_PORT, user=None, pword=None):
    Database.__init__(self, host, port, user, pword)

  def get_connection(self):
    return self.get_cluster().connect(self.KEYSPACE)

  def exec_query(self, query, read=False):
    if read:
      future = self.connection.execute_async(query)
      rows = future.result()
      rows = json.dumps(rows)
      # debug('result:')
      # debug(rows)
      return rows
    else:
      for q in query.split(';'):
        self.connection.execute(q)
      return True

  def initialize(self):
    session = self.get_cluster().connect()
    session.execute("CREATE KEYSPACE IF NOT EXISTS " + self.KEYSPACE + " WITH REPLICATION = { 'class': 'SimpleStrategy', 'replication_factor': 3 };")
    return True

  def check_connectivity(self):
    self.query('SELECT now() FROM system.local')

  def get_cluster(self):
    auth = PlainTextAuthProvider(username=self.user, password=self.pword) if self.user else None
    return Cluster(self.host.split(','), auth_provider=auth)


# Welcome page
class index:
  def GET(self):
    return open('index.html').read()


# Request handlers
class TableManager:

  def GET(self):
    # TO-DO: get schema info for all tables
    return ''

  def POST(self, table):
    req = json.loads(web.data())
    sql = DB.get_cmd_create_table(table, req)
    if check_no_op(web):
      return sql
    return '' if DB.query(sql) else web.badrequest()

  def DELETE(self, table):
    sql = DB.get_cmd_delete_table(table)
    if check_no_op(web):
      return sql
    return '' if DB.query(sql) else web.badrequest()


class Table:

  def GET(self, table):
    sql = DB.get_cmd_get_data(table)
    return sql if check_no_op(web) else DB.query(sql, read=True)

  def POST(self, table):
    req = json.loads(web.data())
    sql = DB.get_cmd_insert_data(table, req)
    if check_no_op(web):
      return sql
    return '' if DB.query(sql) else web.badrequest()

  def DELETE(self, table):
    params = web.input(fName=None, fValue=None)
    if not params.fName or not params.fValue:
      msg = 'must provide fName and fValue, corresponding to the field name and value to use in the WHERE clause of the DELETE statement'
      error(msg)
      return web.badrequest(message=msg)
    sql = DB.get_cmd_delete_data(table, params.fName, params.fValue)
    if check_no_op(web):
      return sql
    return '' if DB.query(sql) else web.badrequest()


class checkAlive:
  def GET(self):
    return ''


class checkReady:
  def GET(self):
    return '' if DB.check_health() else web.internalerror()


if __name__ == '__main__':

  # get config from env vars
  DEBUG = os.environ.get('DEBUG', 'false') == 'true'
  DB_PROVIDER = os.environ.get('DB_PROVIDER', 'postgres')
  DB_HOST = os.environ.get('DB_HOST', 'db')
  DB_PORT = os.environ.get('DB_PORT', None)
  DB_USER = os.environ.get('DB_USER', None)
  DB_PASS = os.environ.get('DB_PASS', None)

  # find Database provider class, create database object
  DB_PROVIDER_CLASS = Database.get_db_class(DB_PROVIDER)
  if not DB_PROVIDER_CLASS:
    fatal('unsupported database provider: ' + DB_PROVIDER + ', please choose from: ' + json.dumps(
      [cl.PROVIDER for cl in Database.__subclasses__()]))
  if DB_PORT:
    if DB_USER:
      DB = DB_PROVIDER_CLASS(DB_HOST, port=DB_PORT, user=DB_USER, pword=DB_PASS)
    else:
      DB = DB_PROVIDER_CLASS(DB_HOST, port=DB_PORT)
  else:
    if DB_USER:
      DB = DB_PROVIDER_CLASS(DB_HOST, user=DB_USER, pword=DB_PASS)
    else:
      DB = DB_PROVIDER_CLASS(DB_HOST)
  if not DB.initialize():
    fatal('unable to initialize the database')
  if not DB.connect():
    fatal('unable to connect to the database')

  # map uris to classes
  urls = (
    '/', 'index',
    '/tables/manage', 'TableManager',
    '/tables/manage/(.*)', 'TableManager',
    '/tables/(.*)', 'Table',
    CHECK_ALIVE_PATH, 'checkAlive',
    CHECK_READY_PATH, 'checkReady'
  )
  app = web.application(urls, globals())

  # collect and expose request/response metrics
  if os.environ.get('EXPOSE_METRICS', 'true') != 'false':
    REQUEST_COUNT = prometheus_client.Counter('requests', 'Request Count', ['method', 'path', 'status'])
    REQUEST_LATENCY = prometheus_client.Histogram('request_latency', 'Request Latency', ['method', 'path'])
    app.add_processor(web.loadhook(before_request))
    app.add_processor(web.unloadhook(after_request))
    prometheus_client.start_http_server(8000)

  # start http server
  web.httpserver.runsimple(app.wsgifunc(), ('0.0.0.0', 80))
