import http from 'k6/http';
import { SharedArray } from 'k6/data';
import { check, sleep } from 'k6';
import { getBaseUrl, getJsonHeaders } from '../helpers/http.js';

const LATENCY_P95 = 300;
const LATENCY_P99 = 500;

const testData = new SharedArray('verification patch data', () => {
  const data = JSON.parse(open('../data/verification_patch.json'));
  if (!Array.isArray(data) || data.length === 0) {
    throw new Error('verification_patch.json is empty or invalid');
  }
  return data;
});

export const options = {
  scenarios: {
    load: {
      executor: 'constant-vus',
      vus: 5,
      duration: '2m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: [`p(95)<${LATENCY_P95}`, `p(99)<${LATENCY_P99}`],
  },
};

export default function () {
  const vuIndex = __VU - 1;
  const stride = 5;
  const localIter = __ITER;
  const globalIndex = vuIndex + (localIter * stride);

  if (globalIndex >= testData.length) {
    return;
  }

  const item = testData[globalIndex];
  const url = `${getBaseUrl()}/api/v1/verifications/${item.verification_id}`;
  const payload = JSON.stringify({ otp_code: item.otp_code });

  const res = http.patch(url, payload, {
    headers: getJsonHeaders(),
    tags: { name: 'PATCH_verification_by_id' },
  });

  check(res, {
    'status is 200': (r) => r.status === 200,
    [`response time < ${LATENCY_P95}ms`]: (r) => r.timings.duration < LATENCY_P95,
  });

  sleep(2.5);
}
