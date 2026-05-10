# Remediation Checklist — inc-91d64890
**Overall Severity:** P1  |  **Issues:** 4

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Throttle or temporarily shed non-essential /api/v1/payments traffic at api-gateway to reduce pressure on payment-service while postgres-primary is at active_connections=195/200 and payment requests are timing out with 504s.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-traffic-shed`

- [ ] **Step 2:** Inspect payment-service connection pool usage for the failing transaction path that logs error_code=DB_CONN_TIMEOUT on order_id=ORD-78219, and reduce concurrent DB calls if the pool is sized too close to postgres-primary max_connections=200.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `pg-pool-exhaustion`

- [ ] **Step 3:** Scale postgres-primary capacity or add a read/write safe connection-pooler capacity adjustment only if available in the current architecture, since wait_event=ClientRead and active_connections=195 indicate the database is near exhaustion.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `postgres-connection-scaling`

- [ ] **Step 4:** Review payment-service release changes and runtime metrics around 2026-05-09T10:01:12Z to identify whether the DB_CONN_TIMEOUTs are caused by a slow transaction path or excessive per-request connection creation.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `payment-db-timeout-investigation`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Immediately restart or roll the failing pod payment-service-7d9f84c9b6-rx2pm in namespace=prod only after confirming the crash loop is due to OOMKilled and Java heap space errors, to restore service availability.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-oom-recovery`

- [ ] **Step 2:** Increase the payment-service memory limit/request for the prod deployment because kubelet reports reason=CrashLoopBackOff, java.lang.OutOfMemoryError: Java heap space, and event=OOMKilled on the same pod.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-memory-limit-tuning`

- [ ] **Step 3:** Adjust the Java heap settings for payment-service so the heap fits within the Kubernetes memory limit in namespace=prod, preventing repeated OOMKilled restarts of payment-service-7d9f84c9b6-rx2pm.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `java-heap-rightsizing`

- [ ] **Step 4:** Inspect recent payment-service memory regressions by comparing the failing pod's runtime behavior before and after restart_count=3 to identify leaked objects, large caches, or request spikes that triggered the OOM condition.
  - Owner: `Service owner`  |  Est. time: 35 min  |  Runbook: `oom-root-cause-analysis`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Reduce load on auth-service by temporarily limiting high-volume token validation traffic through api-gateway while redis-prod-01 GET session:98281 is taking 2740 ms and auth-service returns TOKEN_VALIDATION_FAILED with status=401.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `auth-traffic-protection`

- [ ] **Step 2:** Check redis-cache instance redis-prod-01 for latency spikes, slow commands, and saturation, because session lookups are timing out during GET operations and causing authentication failures.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `redis-latency-triage`

- [ ] **Step 3:** Validate auth-service token-validation configuration and Redis client timeout settings so the session lookup timeout aligns with observed Redis command latency exceeded threshold events.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `auth-redis-timeout-tuning`

- [ ] **Step 4:** Investigate why redis-cache GET latency for session:98281 is 2740 ms by reviewing redis-prod-01 resource usage, eviction pressure, and any recent data growth affecting auth-service token validation.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `redis-root-cause-analysis`


## DEPLOY_FAILURE — P1
**Services:** payment-service, deployment-controller, kubernetes

- [ ] **Step 1:** Rollback deployment payment-service from version v2.8.4 to previous_version=v2.8.3 in namespace=prod because deployment-controller reports error rate increased after deployment and available_replicas=1 of desired_replicas=6.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-rollback-deployment`

- [ ] **Step 2:** Pause further rollout of payment-service v2.8.4 and keep the stable replica set from v2.8.3 serving traffic until available_replicas returns to the desired_replicas=6 threshold.
  - Owner: `Deployment controller owner`  |  Est. time: 5 min  |  Runbook: `rollout-pause-recovery`

- [ ] **Step 3:** Compare change_id=CHG-9182 against v2.8.3 to identify the exact payment-service changes that correspond to the post-deploy error spike and degraded availability.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `deployment-regression-analysis`

- [ ] **Step 4:** Re-deploy payment-service v2.8.4 only after fixing the regression and confirming the rollout can reach 6/6 available replicas without reproducing the increased error rate.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `safe-redeploy-validation`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
