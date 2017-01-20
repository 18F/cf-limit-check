#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time

import schedule
import marshmallow as ma
from webargs import fields
from awslimitchecker.checker import AwsLimitChecker
import requests

class Config(ma.Schema):
    region = fields.Str(load_from='AWS_DEFAULT_REGION', required=True)
    access_key_id = fields.Str(load_from='AWS_ACCESS_KEY_ID', required=True)
    secret_access_key = fields.Str(load_from='AWS_SECRET_ACCESS_KEY', required=True)
    services = fields.DelimitedList(fields.Str, load_from='SERVICES', required=True)
    use_ta = fields.Bool(load_from='USE_TA', missing=True)
    slack_url = fields.Str(load_from='SLACK_URL', required=True)
    slack_channel = fields.Str(load_from='SLACK_CHANNEL', required=True)
    slack_icon = fields.Str(load_from='SLACK_ICON', required=True)

def check(config):
    checker = AwsLimitChecker(region=config['region'])
    warnings, errors = [], []
    for service in config['services']:
        result = checker.check_thresholds(service=service, use_ta=config['use_ta'])
        w, e = process_result(result)
        warnings.extend(w)
        errors.extend(e)
    parts = []
    if warnings:
        parts.append('Warnings:\n{}'.format('\n'.join(warnings)))
    if errors:
        parts.append('Errors:\n{}'.format('\n'.join(errors)))
    if parts:
        requests.post(
            config['slack_url'],
            json={
                'channel': config['slack_channel'],
                'icon_url': config['slack_icon'],
                'text': '\n\n'.join(parts),
            },
        ).raise_for_status()

def process_result(result):
    warnings, errors = [], []
    for service, svc_limits in result.items():
        for limit_name, limit in svc_limits.items():
            for warn in limit.get_warnings():
                warnings.append("{service} '{limit_name}' usage ({u}) exceeds "
                    "warning threshold (limit={l})".format(
                        service=service,
                        limit_name=limit_name,
                        u=str(warn),
                        l=limit.get_limit(),
                    )
                )
            for crit in limit.get_criticals():
                errors.append("{service} '{limit_name}' usage ({u}) exceeds "
                    "critical threshold (limit={l})".format(
                        service=service,
                        limit_name=limit_name,
                        u=str(crit),
                        l=limit.get_limit(),
                    )
                )
    return warnings, errors

if __name__ == "__main__":
    config = Config(strict=True).load(os.environ).data
    schedule.every().day.do(check, config)
    while True:
        schedule.run_pending()
        time.sleep(1)
