import http from 'k6/http';
import { SharedArray } from 'k6/data';
import { check, sleep } from 'k6';
import { getBaseUrl, getJsonHeaders } from '../helpers/http.js';

const LATENCY_P95 = 300;

const testData = new SharedArray('verification patch data', () => {
  const data = JSON.parse(open('../data/verification_patch.json'));
  if (!Array.isArray(data) || data.length === 0) {
    throw new Error('verification_patch.json is empty or invalid');
  }
  return data;
});

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
  const index = __ITER;
  if (index >= testData.length) {
    return;
  }

  const item = testData[index];
  const url = `${getBaseUrl()}/api/v1/verifications/${item.verification_id}`;
  const payload = JSON.stringify({ otp_code: item.otp_code });

  const res = http.patch(url, payload, { headers: getJsonHeaders() });

  check(res, {
    'status is 200': (r) => r.status === 200,
    [`response time < ${LATENCY_P95}ms`]: (r) => r.timings.duration < LATENCY_P95,
    'has verification_token field': (r) => {
      try {
        const body = r.json();
        return typeof body.verification_token === 'string' && body.verification_token.length === 43;
      } catch {
        return false;
      }
    },
    'has expires_in field': (r) => {
      try {
        const body = r.json();
        return typeof body.expires_in === 'number' && body.expires_in > 0;
      } catch {
        return false;
      }
    },
    'content-type is application/json': (r) => {
      const ct = r.headers['Content-Type'] || r.headers['content-type'] || '';
      return ct.includes('application/json');
    },
  });

  sleep(0.1);
}
