#!/usr/bin/env python3

import os
import re
import arrow
import logging
import json
import time
import asyncio
from homeassistant_api import Client

from flask import Flask, Response, request, abort, redirect, jsonify

is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "")
if is_gunicorn:
    from prometheus_flask_exporter.multiprocess import GunicornInternalPrometheusMetrics as PrometheusMetrics
else:
    from prometheus_flask_exporter import PrometheusMetrics

from prometheus_client import Counter, Gauge

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)

app = Flask(__name__)

metrics = PrometheusMetrics(app)

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

@app.route('/entities')
def entities_route():
    return jsonify(get_entities())

@app.route('/entities/<path:path>')
def entities_path_route(path):
    return jsonify(get_entities(path))

@app.route('/script')
def script_route():
    return jsonify(client().get_domain('script').model_dump()['services'])

@app.route('/script/<path:name>')
def script_path_route(name):
    s = getattr(client().get_domain('script'), name)
    return jsonify(s.model_dump())

@app.route('/script/<path:name>/trigger', methods=['GET','POST'])
def script_path_trigger_route(name):
    s = getattr(client().get_domain('script'), name)
    data = {**request.values, **(request.json if request.is_json else {})}
    if s:
        print(f'triggering {name=} with {data=}')
        ret = s.trigger(**data)
        print(f'{ret=}')
        return jsonify([k.model_dump() if getattr(k, 'model_dump') else k for k in ret])
    else:
        abort(404, 'invalid script name')


@app.route('/healthz')
def healthz_route():
    return 'ok'