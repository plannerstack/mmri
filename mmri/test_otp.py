#!/usr/bin/env python
#
# Test OpenTripPlanner

import argparse
from datetime import datetime
import json
import logging
import requests
import sys


DEFAULT_URL = 'http://localhost:8080/opentripplanner-api-webapp/ws/plan'
DATE_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
MAX_COMPUTATION_TIME = 3000
TIMEOUT = 5000 # milliseconds

ERRORS_FOUND = 0
HIGHEST_COMPUTATION_TIME = 0 # milliseconds

logger = logging.getLogger('test-otp')


def test_otp(options):
    infile  = open(options.input,  'r')    if options.input  != '-' else sys.stdin
    outfile = open(options.output, 'w', 1) if options.output != '-' else sys.stdout

    tests = json.load(infile)
    for i, test in enumerate(tests):
        outfile.write(',\n' if i > 0 else '[\n')
        logger.info("Test %d: from %s (%f, %f) to %s (%f, %f)", test['id'],
                test['from']['description'], test['from']['latitude'], test['from']['longitude'],
                test['to']['description'], test['to']['latitude'], test['to']['longitude'])
        url = build_url(test, options)
        logger.debug("Calling URL: %s", url)
        try:
            response = requests.get(url, timeout=options.requesttimeout/1000) 
            resultjson = response.json()
        except requests.exceptions.RequestException as e:    # This is the correct syntax
            logger.debug(e)
            resultjson = {}
        result = parse_result(test, resultjson)
        json.dump(result, outfile, indent=2, sort_keys=True)
        if options.validate:
            validate_result(result)
    outfile.write('\n]\n')

    if options.validate:
        print_validation(options, outfile)

    if infile  is not sys.stdin:  infile.close()
    if outfile is not sys.stdout: outfile.close()


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
    if not result:
        return parse_error(test, result)

    if result['error'] is None:
        return parse_itinerary(test, result)
    else:
        return parse_error(test, result)


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

def validate_result(result):
    global ERRORS_FOUND
    global HIGHEST_COMPUTATION_TIME

    OTPTotalComputationTime = result.get('OTPTotalComputationTime')
    if result.get('isError'):
        ERRORS_FOUND += 1
    if not isinstance( OTPTotalComputationTime, ( int, long ) ):
        ERRORS_FOUND += 1
        logger.debug("validate_result:: No OTPTotalComputationTime found, validation can't succeed")
        return
    if (OTPTotalComputationTime > HIGHEST_COMPUTATION_TIME):
        HIGHEST_COMPUTATION_TIME = OTPTotalComputationTime
    return

def print_validation(options, outfile):
    global ERRORS_FOUND
    global HIGHEST_COMPUTATION_TIME
    successMessage = 'VALIDATION_SUCCESS'
    errorMessage = 'VALIDATION_ERROR'
    errorsFound = ERRORS_FOUND > 0
    maxReached = HIGHEST_COMPUTATION_TIME > options.maxcomputationtime
    message = successMessage
    if (errorsFound or maxReached):
        message = errorMessage
    outfile.write(message)
    logger.debug('%s - ERRORS_FOUND: %s, HIGHEST_COMPUTATION_TIME: %s', message, ERRORS_FOUND, HIGHEST_COMPUTATION_TIME)
    return message

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
    parser.add_argument('-v', '--validate', action='store_true',
            help='validate the results. Outputs VALIDATION_SUCCESS at the end of the output if no errors were returned and all test had a OTPTotalComputationTime underneath maxcomputationtime, else VALIDATION_ERROR')
    parser.add_argument('-m', '--maxcomputationtime', default=MAX_COMPUTATION_TIME, type=int,
            help='the maxmimum time (in ms) that a request is allowed to have taken (default: ' + str(MAX_COMPUTATION_TIME) + ')')
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
