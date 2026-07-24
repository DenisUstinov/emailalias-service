import http from 'k6/http';
import { check } from 'k6';
import { getBaseUrl, getJsonHeaders } from '../helpers/http.js';
import { generateRandomEmail } from '../helpers/random.js';

const LATENCY_P95 = 500;
const LATENCY_P99 = 1000;

export const options = {
  scenarios: {
    load: {
      executor: 'constant-arrival-rate',
      rate: 2,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 5,
      maxVUs: 10,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: [`p(95)<${LATENCY_P95}`, `p(99)<${LATENCY_P99}`],
  },
};

export default function () {
  const payload = JSON.stringify({
    email: generateRandomEmail(),
    action_type: 'user_creation',
  });

  const res = http.post(`${getBaseUrl()}/api/v1/verifications`, payload, {
    headers: getJsonHeaders(),
    tags: { name: 'POST_verifications' },
  });

  check(res, {
    'status is 202': (r) => r.status === 202,
    [`response time < ${LATENCY_P95}ms`]: (r) => r.timings.duration < LATENCY_P95,
  });
}
