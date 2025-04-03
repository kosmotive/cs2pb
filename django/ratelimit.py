import itertools
import logging
import time

import requests

log = logging.getLogger(__name__)


class RequestError(Exception):

    def __init__(self, status_code=None):
        self.status_code = status_code


class Ratelimiter:

    def __init__(self, service_name=None, baserate=10, accel=1.1, ratedecay=0.5, ratebreak=2, max_trycount=10):
        self.service_name = service_name
        self.baserate = baserate
        self.rate = baserate
        self.accel = accel
        self.ratedecay = ratedecay
        self.ratebreak = ratebreak
        self.last_request_time = 0
        self.max_trycount = max_trycount

    def __str__(self):
        return 'Rate limit' if self.service_name is None else f'Rate limit for {self.service_name}'

    def request(self, url, method='get', accept=(200,), **kwargs):
        """Performs HTTP request.
        """
        log.debug(f'{method.upper()} {url}, {str(kwargs)}')

        # set default timeout to 10 seconds
        kwargs = dict(kwargs)
        kwargs.setdefault('timeout', 10)

        # enforce the rate limit
        dt = time.time() - self.last_request_time
        min_dt = 1 / self.rate
        time.sleep(max((0, min_dt - dt)))
        self.last_request_time = time.time()

        for trycount in itertools.count(1):
            if trycount > self.max_trycount:
                raise RequestError()

            log.debug(f'-> trycount: {trycount} / {self.max_trycount}')

            # do the request
            try:
                response = getattr(requests, method)(url=url, **kwargs)
            except requests.exceptions.Timeout:
                log.debug('  -> timeout')
                continue

            # handle the response
            log.debug(f'  -> {str(response)}')
            if response is not None and response.status_code not in accept:
                raise RequestError(response.status_code)
            if response:

                # increase the rate but don't exceed the server-enforced rate limit
                actual_request_dt = time.time() - self.last_request_time
                self.rate = max((self.rate * self.accel, 1 / actual_request_dt))
                return response

            # we probably hit the rate limit
            waittime = trycount * self.ratebreak
            print(f'{str(self)} hit at {self.rate:.0f} req/s, waiting {waittime:.1f} s')
            self.rate = max((self.baserate, self.rate * self.ratedecay))
            time.sleep(waittime)
