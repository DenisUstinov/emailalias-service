// NOTE: Для прохождения этого теста необходимо, задать rate_limit='1/s' на задачу send_otp_task.
import http from 'k6/http';
import { Counter } from 'k6/metrics';
import { getBaseUrl, getJsonHeaders } from '../helpers/http.js';
import { hasProblemJsonContract } from '../helpers/assertions.js';
import { generateRandomEmail } from '../helpers/random.js';

const unexpectedStatus = new Counter('unexpected_status');
const protectedByApp = new Counter('protected_by_app_503');

let queueLimitReached = false;

export const options = {
  scenarios: {
    stress: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 100,
      maxVUs: 300,
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
    headers: getJsonHeaders(),
  });

  if (res.status === 202) {
    return;
  }

  if (res.status === 503) {
    protectedByApp.add(1);
    queueLimitReached = true;
    void hasProblemJsonContract(res);
  } else {
    unexpectedStatus.add(1, { status: res.status.toString() });
  }
}
