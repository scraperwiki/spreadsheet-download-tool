#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests  # requires Python requests 1.x
import traceback # for formatting exceptions
import json # for decoding API responses
import collections # for parsing JSON as ordereddicts
from tempfile import mkstemp
from datetime import datetime
import os
from os.path import join, abspath, dirname
import scraperwiki

def main():
    box_url = get_box_url()
    tables = get_dataset_tables(box_url)
    grids = get_dataset_grids(box_url)

    save_state('all_tables.xls', None, None, 'generating')

    for table in tables:
        save_state('{}.csv'.format(table['name']), 'table', table['name'], 'waiting')

    for grid in grids:
        save_state('{}.csv'.format(grid['name']), 'grid', grid['name'], 'waiting')


def get_dataset_tables(box_url):
    tables = []
    database_meta = get_database_meta(box_url)
    for table_name, table_meta in database_meta['table'].items():
        if not table_name.startswith('_'):
            tables.append({
                'id': table_name,
                'name': table_name,
                'columns': table_meta['columnNames']
            })
    return tables


def get_dataset_grids(box_url):
    grids = []
    try:
        results = query_sql_database(box_url, 'SELECT * FROM _grids')
        for result in results:
            grids.append({
                'id': result['checksum'],
                'name': result['title'],
                'url': result['url']
            })
    except Exception as e:
        log('could not get _grids:')
        log(e)
    return grids


def log(string):
    print string


def get_box_url():
    filename = abspath(join(dirname(__file__), '..', 'dataset_url.txt'))
    try:
        with open(filename, 'r') as f:
            return f.read().strip()
    except IOError:
        raise RuntimeError("ERROR: No dataset URL in {}".format(filename))


def call_api(box_url, params=None):
    # returns sql api output as a Python dict/list
    response = requests.get(box_url, params=params)
    log("GET %s" % response.url)
    if response.status_code == requests.codes.ok:
        return json.loads(response.content,
                          object_pairs_hook=collections.OrderedDict)
    else:
        response.raise_for_status()


def query_sql_database(box_url, query):
    return call_api("%s/sql" % box_url, {"q": query})


def get_database_meta(box_url):
    return call_api("%s/sql/meta" % box_url)


def save_state(filename, source_type, source_id, state):
    log("%s %s" % (filename, state))
    if state in ['generating', 'waiting', 'failed']:
        scraperwiki.sql.save(['filename'], {
            'filename': filename,
            'state': state,
            'created': None,
            'source_type': source_type,
            'source_id': source_id
        }, '_state')
    elif state == 'generated':
        scraperwiki.sql.save(['filename'], {
            'filename': filename,
            'state': 'generated',
            'created': '{}+00:00'.format(datetime.now().isoformat()),
            'source_type': source_type,
            'source_id': source_id
        }, '_state')
    else:
        raise Exception("Unknown status: %s" % state)


try:
    main()
except Exception as e:
    print('Error while extracting your dataset: %s' % e)
    scraperwiki.sql.save(
        unique_keys=['message'],
        data={'message': traceback.format_exc()},
        table_name='_error')
    raise





