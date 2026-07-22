import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';
import { getBaseUrl, getJsonHeaders, generateRandomEmail } from '../helpers.js';

const unexpectedStatus = new Counter('unexpected_status');
const protectedByNginx = new Counter('protected_by_nginx_429');
const protectedByApp = new Counter('protected_by_app_503');
const wrongContentType503 = new Counter('wrong_content_type_503');

let queueLimitReached = false;

export const options = {
  scenarios: {
    stress: {
      executor: 'constant-arrival-rate',
      rate: 20,
      timeUnit: '1s',
      duration: '50s',
      preAllocatedVUs: 20,
      maxVUs: 50,
    },
  },
  thresholds: {
    'unexpected_status': ['count==0'],
    'protected_by_app_503': ['count>0'],
  },
};

export default function () {
  if (queueLimitReached) {
    return;
  }

  const payload = JSON.stringify({
    email: generateRandomEmail(),
    action_type: 'user_creation',
  });

  const res = http.post(`${getBaseUrl()}/api/v1/verifications`, payload, {
    headers: {
      ...getJsonHeaders(),
      'X-Load-Test': 'true',
    },
  });

  if (res.status === 202) {
    return;
  }

  if (res.status === 429) {
    protectedByNginx.add(1);
    return;
  }

  if (res.status === 503) {
    protectedByApp.add(1);
    queueLimitReached = true;

    const ct = res.headers['Content-Type'] || res.headers['content-type'] || '';
    if (!ct.includes('application/problem+json')) {
      wrongContentType503.add(1);
    }

    check(res, {
      '503_has_problem_json_contract': () => ct.includes('application/problem+json'),
    });
  } else {
    unexpectedStatus.add(1, { status: res.status.toString() });
  }
}
