#!/usr/bin/env python
#
# Test OpenTripPlanner
import os
import argparse
from datetime import datetime
import time
import json
import logging
import requests
import sys

# DEFAULTS
DEFAULT_URL = 'http://localhost:8080/opentripplanner-api-webapp/ws/plan'
DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
TIMEOUT = 5000 # milliseconds

# GLOBAL USED FOR KEEPING TRACK OF VALIDATION
VALIDATION = {}

logger = logging.getLogger('test-otp')

# CONFIG FOR GRAYLOG2
GELFHOST = None #'54.89.119.236'
GELFPORT = None # 49154

if (GELFHOST and GELFPORT):
    try:
        # $ pip install gelfHandler
        # From: https://github.com/stewrutledge/gelfHandler/
        from gelfHandler import gelfHandler
        gHandler = gelfHandler(host=GELFHOST,port=GELFPORT,proto='UDP')
        logger.addHandler(gHandler)
    except ImportError:
        logger.warn("GelfHandler not importer, not logging to Gelf server")


def test_otp(options):
    instream  = open(options.input,  'r')    if options.input  != '-' else sys.stdin
    outstream = open(options.output, 'w', 1) if options.output != '-' else sys.stdout

    tests = json.load(instream)
    before_all_tests(tests, options)

    for i, test in enumerate(tests):
        before_each_test(test, options, i) # adds test['url'] and test['test_identifier']

        # OUT: start of array or seperator
        outstream.write(',\n' if i > 0 else '[\n')

        logger.info('RUNNING: %s on %s' % (test['test_identifier'], test['url']), extra={'gelfProps':{'test':test['test_identifier'], 'url': test['url']}})

        try:
            response = requests.get(test['url'], timeout=options.requesttimeout/1000) 
            resultjson = response.json()
        except requests.exceptions.RequestException as e:    # This is the correct syntax
            logger.error('REQUESTEXCEPTION: %s on %s' % (test['test_identifier'], test['url']), extra={'gelfProps':{'test':test['test_identifier'], 'url': test['url'], 'requestException': str(e)}})
            resultjson = {}

        result = parse_result(test, resultjson)

        # OUT: actual result
        json.dump(result, outstream, indent=2, sort_keys=True)

        after_each_test(test, result, options, i)

    after_all_tests(tests, options)

    # OUT: end of array
    outstream.write('\n]\n')

    if instream  is not sys.stdin:  instream.close()
    if outstream is not sys.stdout: outstream.close()


def before_all_tests(tests, options):
    VALIDATION['startTime'] = int(round(time.time() * 1000))
    VALIDATION['errorsFound'] = 0
    VALIDATION['highestTestDuration'] = 0

    logger.info('BEFOREALLTESTS %s' % options.url,
        extra={'gelfProps':{
            'startTimestamp':       VALIDATION['startTime']
        }})
    
def after_all_tests(tests, options):
    VALIDATION['endTime'] = int(round(time.time() * 1000))
    VALIDATION['totalTestDuration'] = (VALIDATION['endTime'] - VALIDATION['startTime'])
    
    logger.info('AFTERALLTESTS %s: %s' % (options.url, VALIDATION['totalTestDuration']),
        extra={'gelfProps':{ 
            'url':                  options.url,
            'startTimestamp':       VALIDATION['startTime'],
            'endTimestamp':         VALIDATION['endTime'],
            'totalTestDuration':    VALIDATION['totalTestDuration'],
            'errorsFound':          VALIDATION['errorsFound'],
            'highestTestDuration':  VALIDATION['highestTestDuration']
            }})

    if options.output:
        fileName, fileExtension = os.path.splitext(options.output)
        validationOutputName = '%s_validation%s' % (fileName, fileExtension)
        validationOutput = open(validationOutputName, 'w', 1)
        json.dump(VALIDATION, validationOutput, indent=2, sort_keys=True)
        validationOutput.close()



def before_each_test(test, options, i):
    # Extend test object with url and test_identifier
    test['test_identifier'] = readable_test_identifier(test)
    test['url'] = build_url(test, options)

    VALIDATION[test['id']] = {
        'id':               test['id'],
        'startTime':        int(round(time.time() * 1000)),
        'url':              test['url'],
        'test_identifier':  test['test_identifier']
    }


def after_each_test(test, result, options, i):
    VALIDATION[test['id']]['endTime'] = int(round(time.time() * 1000))
    VALIDATION[test['id']]['testDuration'] = (VALIDATION[test['id']]['endTime'] - VALIDATION[test['id']]['startTime'])
    VALIDATION[test['id']]['isError']  = result['isError']
    VALIDATION[test['id']]['itineraryDuration'] = 0 if result['isError'] else result['duration']
    VALIDATION[test['id']]['itineraryTransfers'] = 0 if result['isError'] else result['transfers']

    if (VALIDATION[test['id']]['testDuration'] > VALIDATION['highestTestDuration']):
        VALIDATION['highestTestDuration'] = VALIDATION[test['id']]['testDuration']
    if (result['isError']):
        VALIDATION['errorsFound'] += 1

    logger.info('AFTERTEST %s' % test['id'],
        extra={ 'gelfProps': VALIDATION[test['id']] })



# UTILS
def readable_test_identifier(test):
    return "Test %s: from %s (%s, %s) to %s (%s, %s)" % (test['id'],
    test['from']['description'], test['from']['latitude'], test['from']['longitude'],
    test['to']['description'], test['to']['latitude'], test['to']['longitude'])


def build_url(test, options):
    time = datetime.strptime(test['time'], DATE_TIME_FORMAT)

    if options.today:
        now = datetime.now()
        time = now.replace(hour=time.hour, minute=time.minute)

    coords = lambda c: '%f,%f' % (c['latitude'], c['longitude'])
    params = {
        'fromPlace': coords(test['from']),
        'toPlace': coords(test['to']),
        'date': time.strftime('%Y-%m-%d'),
        'time': time.strftime('%H:%M:%S'),
        'arriveBy': (test['timeType'] == 'A'),
        'maxWalkDistance': 5000,
        'optimize': 'QUICK',
        'mode': 'WALK,TRANSIT',
        'walkSpeed': 1.389,
        'numItineraries': 1,
    }
    url = options.url + '?' + '&'.join('%s=%s' % (k, v) for k, v in params.items())
    return url


def parse_result(test, result):
    if not result or result['error'] is not None:
        return parse_error(test, result)
    else:
        return parse_itinerary(test, result)


def parse_itinerary(test, result):
    itinerary = result.get('plan', {}).get('itineraries')[0]
    return {
        'id': test['id'],
        'isError': False,
        'OTPTotalComputationTime': result.get("debug", {}).get("totalTime"),
        'OTPTimedout': result.get("debug", {}).get("timedOut"),
        'transfers': itinerary['transfers'],
        'departureTime': jsonDateTime(itinerary['startTime']),
        'arrivalTime': jsonDateTime(itinerary['endTime']),
        'duration': itinerary['duration'] / 60,  # seconds to minutes
        'legs': [parse_leg(leg) for leg in itinerary['legs']],
    }


def parse_leg(leg):
    if leg['mode'] == 'WALK':
        line = 'walk'
    else:
        line = '%(route)s (%(headsign)s)' % leg
    return {
        'departureTime': jsonDateTime(leg['startTime']),
        'arrivalTime': jsonDateTime(leg['endTime']),
        'line': line,
    }


def parse_error(test, result):
    return {
        'id': test.get('id'),
        'isError': True,
        'OTPTotalComputationTime': result.get("debug", {}).get("totalTime"),
        'OTPTimedout': result.get("debug", {}).get("timedOut"),
        'error': result.get('error', {}).get('msg'),
    }


def jsonDateTime(timestamp):
    time = datetime.fromtimestamp(timestamp / 1000)  # milliseconds to seconds
    return datetime.strftime(time, DATE_TIME_FORMAT)

# Command line handling

def parse_args(args=None):
    parser = argparse.ArgumentParser(
            description='Test OpenTripPlanner using planning data from a test file.')
    parser.add_argument('input', metavar='INPUT', nargs='?', default='-',
            help='the test input file (default: stdin)')
    parser.add_argument('output', metavar='OUTPUT', nargs='?', default='-',
            help='the test output file (default: stdout')
    parser.add_argument('-u', '--url', metavar='URL', default=DEFAULT_URL,
            help='the OpenTripPlanner URL (default: ' + DEFAULT_URL + ')')
    parser.add_argument('-d', '--debug', action='store_true',
            help='show debugging output')
    parser.add_argument('-t', '--today', action='store_true',
            help='overrule the dates given in the test data to be on today')
    parser.add_argument('-r', '--requesttimeout', default=TIMEOUT, type=int,
            help='the maxmimum time (in ms) that a request is allowed to have taken (default: ' + str(TIMEOUT) + ')')
    return parser.parse_args(args)


def main():
    args = parse_args()

    logging.basicConfig(format='%(message)s', level=logging.WARN)
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    test_otp(args)


if __name__ == '__main__':
    main()
