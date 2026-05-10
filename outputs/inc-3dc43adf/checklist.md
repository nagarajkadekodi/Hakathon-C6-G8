# Remediation Checklist — inc-3dc43adf
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** On postgres-primary for db=payments, immediately relieve connection pressure by finding and terminating runaway or idle-in-transaction sessions contributing to active_connections=195/200 and the "connection pool near exhaustion" state; preserve the connection slot reserved for superuser access by targeting non-superuser backends first.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-pressure-relief`

- [ ] **Step 2:** Reduce pressure on postgres-primary by temporarily scaling down or pausing non-critical payment-service traffic paths that create database sessions, since payment-service is already failing with DB_CONN_TIMEOUT and PSQLException "remaining connection slots are reserved for non-replication superuser connections".
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `payment-db-load-shedding`

- [ ] **Step 3:** Investigate and fix the slow insert on table payment_transactions tied to slow_query_ms=8421 and query_hash=ab91ff, then address the lock wait exceeded threshold at lock_wait_ms=6032 for blocked_query_hash=cd77aa and blocking_pid=4421 by identifying the blocking transaction and the specific SQL path in payment-service.
  - Owner: `Database administrator`  |  Est. time: 30 min  |  Runbook: `postgres-slow-query-lock-wait-investigation`

- [ ] **Step 4:** Tune payment-service database access so it stops exhausting postgres-primary slots: verify connection pool sizing, max pool connections, and request timeout settings against postgres-primary max_connections=200, then restart payment-service only after the pool configuration is reduced and validated.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `payment-db-pool-tuning`

- [ ] **Step 5:** After load stabilizes, confirm payment transaction success rates and that active_connections on postgres-primary remain below the exhaustion threshold while payment-service no longer emits DB_CONN_TIMEOUT or "Unable to initialize payment due to database connection failure" errors.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `payment-db-recovery-validation`


## OOM_KILL — P1
**Services:** payment-service, payment-service-7d9f84c9b6-rx2pm

- [ ] **Step 1:** Immediately stop the CrashLoopBackOff on pod payment-service-7d9f84c9b6-rx2pm in namespace prod by scaling payment-service to a stable replica set or temporarily rolling back traffic to healthy replicas so the OOMKilled container stops restarting.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-crashloop-containment`

- [ ] **Step 2:** Inspect the pod memory limit and Java heap usage for payment-service-7d9f84c9b6-rx2pm after the java.lang.OutOfMemoryError "Java heap space" event, then increase the container memory limit only enough to get below the OOMKilled threshold while preserving headroom for the JVM.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-java-heap-rightsize`

- [ ] **Step 3:** Adjust JVM options for payment-service so heap sizing matches the Kubernetes memory limit and prevents heap-space exhaustion; verify the new settings before redeploying to prod namespace prod.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `jvm-heap-container-sizing`

- [ ] **Step 4:** Review recent allocation-heavy payment-service code paths that could trigger repeated OOMKilled restarts, focusing on the request path active when restart_count=3 and the container was killed for memory limit exceeded.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `payment-memory-leak-investigation`

- [ ] **Step 5:** Redeploy payment-service after memory settings are corrected and confirm the pod no longer enters CrashLoopBackOff and the Kubernetes event stream no longer reports OOMKilled for payment-service-7d9f84c9b6-rx2pm.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-oom-recovery`


## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** On postgres-primary, identify and stop the transaction behind blocking_pid=4421 that is causing the lock_wait_ms=6032 on blocked_query_hash=cd77aa, because it is directly delaying payment initialization and contributing to PAYMENT_INIT_FAILED in payment-service.
  - Owner: `Database administrator`  |  Est. time: 10 min  |  Runbook: `postgres-blocking-lock-release`

- [ ] **Step 2:** Investigate the slow insert on table payment_transactions with slow_query_ms=8421 and query_hash=ab91ff, then add or fix the missing index or query shape that is making inserts slow under load.
  - Owner: `Database administrator`  |  Est. time: 35 min  |  Runbook: `postgres-slow-insert-optimization`

- [ ] **Step 3:** Reduce concurrent write pressure from payment-service while the contention is active by temporarily throttling payment transaction creation paths that are failing with "Unable to initialize payment due to database connection failure".
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `payment-write-throttle`

- [ ] **Step 4:** Validate postgres-primary transaction settings and lock timeout behavior for db=payments so future lock waits are surfaced sooner and do not cascade into payment-service connection failures.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-lock-timeout-tuning`

- [ ] **Step 5:** Confirm payment-service can initialize new payments successfully after the lock contention is resolved and verify no further slow_query_ms or lock_wait_ms alerts appear on postgres-primary.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `payment-db-recovery-validation`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Check redis-cache instance redis-prod-01 immediately and reduce session lookup latency by identifying whether the GET key=session:98281 path is impacted by saturation, because latency_ms=2740 is causing auth-service TOKEN_VALIDATION_FAILED and api-gateway 401s.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `redis-latency-triage`

- [ ] **Step 2:** If redis-prod-01 is overloaded, scale or fail over redis-cache to restore low-latency GETs for session validation, since auth-service is timing out on Redis session lookup and api-gateway requests to /api/v1/profile are returning 401 status with 3102 ms latency.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-failover-latency-recovery`

- [ ] **Step 3:** Verify auth-service timeout and retry settings for Redis session validation so transient latency on redis-cache does not immediately surface as status=401 TOKEN_VALIDATION_FAILED.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `auth-redis-timeout-tuning`

- [ ] **Step 4:** Inspect redis-cache health for command latency spikes on GET operations and check for memory pressure, eviction, or network path issues affecting instance redis-prod-01.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `redis-session-latency-investigation`

- [ ] **Step 5:** Validate token validation succeeds end to end by confirming auth-service no longer emits Redis session lookup timeout and api-gateway stops returning authentication failed due to token validation timeout for /api/v1/profile.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `auth-flow-recovery-validation`


## DEPLOY_FAILURE — P2
**Services:** deployment-controller, payment-service

- [ ] **Step 1:** Immediately pause further rollout of payment-service version v2.8.4 in namespace prod because deployment-controller detected a recent deployment within 30 minutes and error rate increased after change_id=CHG-9182.
  - Owner: `Release engineer`  |  Est. time: 5 min  |  Runbook: `deployment-freeze`

- [ ] **Step 2:** Rollback payment-service from v2.8.4 to previous_version=v2.8.3 to restore availability while available_replicas=1/desired_replicas=6 and reduce the elevated error rate introduced by the recent deployment.
  - Owner: `Release engineer`  |  Est. time: 10 min  |  Runbook: `k8s-deployment-rollback`

- [ ] **Step 3:** Confirm the healthy replica set is serving traffic after rollback by checking that deployment payment-service in prod recovers available_replicas toward desired_replicas=6 and no longer shows deployment availability below threshold.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `deployment-rollout-validation`

- [ ] **Step 4:** Compare v2.8.4 against v2.8.3 for the specific config or code changes tied to change_id=CHG-9182, focusing on payment-service error spikes that started after deployment.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `release-regression-analysis`

- [ ] **Step 5:** Only resume rollout after fixing the identified regression and verify deployment-controller no longer reports elevated errors after deployment for payment-service v2.8.4.
  - Owner: `Release engineer`  |  Est. time: 20 min  |  Runbook: `deployment-retry-after-fix`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
