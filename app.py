#!/usr/bin/env python3

import os
import re
import arrow
import logging
import json
import time
import asyncio
from homeassistant_api import Client
from homeassistant_api.errors import RequestError

import werkzeug.exceptions

def get_body(self, environ=None, scope=None):
    if self.description:
        return f'HTTP {self.code} {self.name}: {self.description}'
    return f'HTTP {self.code} {self.name}'

werkzeug.exceptions.HTTPException.get_body = get_body

from flask import Flask, Response, request, abort, redirect, jsonify

is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)

app = Flask(__name__)


HA_API_URL = os.getenv('HA_API_URL')
HA_TOKEN = os.getenv('HA_TOKEN')

def client():
    return Client(HA_API_URL, HA_TOKEN)

@app.route('/')
def index():
    return jsonify(
        {}
    )

def get_entities(path=None):
    e = {k: v.model_dump() for k,v in client().get_entities().items()}
    if path:
        parts = re.split('\.|/', path)
        for a in parts:
            e = e.get(a)
            if not e:
                break
            if type(e) == dict and 'entities' in e.keys() and not 'entities' in parts:
                e = e.get('entities')
    return e

def get_services(path=None):
    e = {k: v.model_dump() for k,v in client().get_domains().items()}
    if path:
        parts = re.split('\.|/', path)
        for a in parts:
            e = e.get(a)
            if not e:
                break
            if type(e) == dict and 'services' in e.keys() and not 'services' in parts:
                e = e.get('services')
    return e

@app.route('/entities')
@app.route('/entity')
def entities_route():
    return jsonify(get_entities())

@app.route('/entities/<path:path>')
@app.route('/entity/<path:path>')
def entities_path_route(path):
    return jsonify(get_entities(path))

@app.route('/scripts')
@app.route('/script')
def scripts_route():
    return jsonify(client().get_domain('script').model_dump()['services'])

@app.route('/scripts/<path:name>')
@app.route('/script/<path:name>')
def scripts_path_route(name):
    s = getattr(client().get_domain('script'), name)
    return jsonify(s.model_dump())

@app.route('/scripts/<path:name>/trigger', methods=['GET','POST'])
@app.route('/script/<path:name>/trigger', methods=['GET','POST'])
def scripts_path_trigger_route(name):
    s = getattr(client().get_domain('script'), name)
    data = {**request.values, **(request.json if request.is_json else {})}
    if s:
        print(f'triggering {name=} with {data=}')
        ret = s.trigger(**data)
        print(f'{ret=}')
        return jsonify([k.model_dump() if getattr(k, 'model_dump') else k for k in ret])
    else:
        abort(404, 'invalid script name')

@app.route('/service')
@app.route('/services')
def services_route():
    return jsonify(get_services())

@app.route('/service/<path:path>')
@app.route('/services/<path:path>')
def services_path_route(path):
    return jsonify(get_services(path))

@app.route('/service/<path:name>/trigger', methods=['GET','POST'])
@app.route('/services/<path:name>/trigger', methods=['GET','POST'])
def services_path_trigger_route(name):
    domain = name.split('/')[0]
    ent = name.split('/')[1:]
    try:
        s = getattr(client().get_domain(domain), ent[0])
        for i in ent[1:]:
            s = getattr(s, i)
    except Exception as e:
        return abort(500, f'error finding service {name=} {domain=} {ent=} {e}')
    data = {**request.values, **(request.json if request.is_json else {})}
    if s:
        print(f'triggering service {name=} with {data=}')
        try:
            ret = s.trigger(**data)
            print(f'{ret=}')
            return jsonify([k.model_dump() if getattr(k, 'model_dump') else k for k in ret])
        except RequestError as e:
            return abort(500, f'error triggering service {name=} with {data=}: {e}')
    else:
        abort(404, 'invalid script name')

@app.route('/healthz')
def healthz_route():
    return 'ok'