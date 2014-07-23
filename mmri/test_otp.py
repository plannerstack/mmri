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
        response = requests.get(url)
        result = parse_result(test, response.json())
        json.dump(result, outfile, indent=2, sort_keys=True)
    outfile.write('\n]\n')

    if infile  is not sys.stdin:  infile.close()
    if outfile is not sys.stdout: outfile.close()


def build_url(test, options):
    time = datetime.strptime(test['time'], DATE_TIME_FORMAT)
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
    if result['error'] is None:
        return parse_itinerary(test, result)
    else:
        return parse_error(test, result)


def parse_itinerary(test, result):
    itinerary = result['plan']['itineraries'][0]
    return {
        'id': test['id'],
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
        'id': test['id'],
        'OTPTotalComputationTime': result.get("debug", {}).get("totalTime"),
        'OTPTimedout': result.get("debug", {}).get("timedOut"),
        'error': result['error']['msg'],
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
    return parser.parse_args(args)


def main():
    args = parse_args()

    logging.basicConfig(format='%(message)s', level=logging.WARN)
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    test_otp(args)


if __name__ == '__main__':
    main()
