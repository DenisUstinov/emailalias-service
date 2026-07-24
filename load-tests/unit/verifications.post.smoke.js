import http from 'k6/http';
import { check, sleep } from 'k6';
import { getBaseUrl, getJsonHeaders } from '../helpers/http.js';
import { generateRandomEmail } from '../helpers/random.js';
import { hasProblemJsonContract } from '../helpers/assertions.js';

const LATENCY_P95 = 500;

export const options = {
  vus: 1,
  iterations: 200,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: [`p(95)<${LATENCY_P95}`],
    checks: ['rate>0.99'],
  },
};

export default function () {
  const payload = JSON.stringify({
    email: generateRandomEmail(),
    action_type: 'user_creation',
  });

  const res = http.post(`${getBaseUrl()}/api/v1/verifications`, payload, {
    headers: getJsonHeaders(),
  });

  check(res, {
    'status is 202': (r) => r.status === 202,
    [`response time < ${LATENCY_P95}ms`]: (r) => r.timings.duration < LATENCY_P95,
    'has verification_id field': (r) => {
      try {
        const body = r.json();
        return typeof body.verification_id === 'string' && body.verification_id.length === 36;
      } catch {
        return false;
      }
    },
    'content-type is application/json': (r) => {
      const ct = r.headers['Content-Type'] || r.headers['content-type'] || '';
      return ct.includes('application/json');
    },
  });

  if (res.status >= 400) {
    hasProblemJsonContract(res);
  }

  sleep(0.1);
}
