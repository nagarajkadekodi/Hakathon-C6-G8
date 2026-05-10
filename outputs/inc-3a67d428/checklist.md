# Remediation Checklist — inc-3a67d428
**Overall Severity:** P1  |  **Issues:** 6

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** On postgres-primary in db=payments, immediately stop non-essential write traffic from payment-service by pausing payment transaction retries and any background job that creates new DB sessions, to relieve the active_connections=195/200 exhaustion and avoid hitting the reserved superuser slots; coordinate via api-gateway if needed to temporarily shed payment POST traffic.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-shedding`

- [ ] **Step 2:** Inspect and terminate the specific long-running transaction holding blocking_pid=4421 that is causing lock_wait_ms=6032 for blocked_query_hash=cd77aa, then re-run the slow insert query identified by query_hash=ab91ff on table=payment_transactions to confirm whether the slow_query_ms=8421 is due to lock contention or query plan regression.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-lock-contention`

- [ ] **Step 3:** Reduce connection pressure on postgres-primary by lowering payment-service JDBC/Hikari pool size so it stays well below max_connections=200, then restart payment-service pods only after the pool cap is applied to prevent repeating FATAL: remaining connection slots are reserved for non-replication superuser connections.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `db-pool-tuning`

- [ ] **Step 4:** Pull postgres-primary logs and metrics for db=payments around 2026-05-09T10:01:13Z-10:02:36Z to identify whether the connection exhaustion is driven by slow inserts, lock waits, or leaked idle sessions, and correlate with payment-service trace_ids a81d11 and d33f81 to find the exact transaction path causing the surge.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `postgres-root-cause-analysis`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Scale payment-service in namespace=prod to add at least one extra replica for pod payment-service-7d9f84c9b6-rx2pm while the container is CrashLoopBackOff and OOMKilled, so api-gateway traffic has a live endpoint while the failing pod is repaired.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-emergency-scale`

- [ ] **Step 2:** Increase the payment-service container memory limit above the current value that is triggering event=OOMKilled and Java heap space, then restart the deployment so the JVM can start without exceeding the Kubernetes memory limit.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-memory-limit-tuning`

- [ ] **Step 3:** Adjust the Java heap settings for payment-service so the heap stays below the pod memory limit after the increase, preventing java.lang.OutOfMemoryError: Java heap space from recurring during payment transaction handling.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `jvm-heap-sizing`

- [ ] **Step 4:** Review recent memory growth in payment-service-7d9f84c9b6-rx2pm around restart_count=3 and correlate heap usage with request handling to determine whether a code path introduced by the current deployment is retaining objects or amplifying allocations under payment load.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `heap-leak-investigation`


## NETWORK_ERROR — P1
**Services:** api-gateway, payment-service

- [ ] **Step 1:** Temporarily reduce api-gateway retries for POST /api/v1/payments to avoid compounding the upstream failure while payment-service is returning 504 and 502 responses with latencies of 12030 ms, 8321 ms, and 15012 ms.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-retry-throttling`

- [ ] **Step 2:** Check payment-service pod health, readiness, and request latency under the current deployment, since api-gateway is timing out on upstream=payment-service and returning bad gateway from upstream; restart or reschedule unhealthy pods that are not responding within the gateway timeout window.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `upstream-health-check`

- [ ] **Step 3:** Verify that payment-service timeouts are not caused by the same DB connection exhaustion seen in postgres-primary; align gateway timeout and payment-service upstream timeout settings only after confirming whether the backend can respond before the current 12-15 second gateway latency.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `timeout-alignment`

- [ ] **Step 4:** Correlate trace_id=a81d11, b12c44, and e19bc1 across api-gateway and payment-service to identify whether the failures are all the same transaction path or separate upstream incidents, then inspect the deployment version and pod logs for recurring 504/502 patterns.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `gateway-upstream-correlation`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Reduce auth-service dependency on redis-prod-01 by temporarily extending token validation grace periods or enabling cached session fallback for GET /api/v1/profile while Redis GET latency is 2740 ms, to stop 401 spikes from token validation timeout.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `auth-degradation-mode`

- [ ] **Step 2:** Inspect redis-cache instance redis-prod-01 for command latency on session:98281 and other session keys, then move the auth session workload off the slow node or restart the impacted Redis instance if it is saturated or unhealthy.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-latency-triage`

- [ ] **Step 3:** Check auth-service timeout and retry settings for Redis session lookups so TOKEN_VALIDATION_FAILED does not occur before a reasonable Redis response window, then redeploy auth-service after tuning to match the observed 2740 ms Redis latency.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `auth-redis-timeouts`

- [ ] **Step 4:** Investigate why redis-cache latency exceeded threshold for GET session:98281 at 2026-05-09T10:02:04Z, including whether there is memory pressure, eviction, or a network bottleneck on redis-prod-01 affecting auth-service and api-gateway 401s.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `redis-root-cause-analysis`


## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Kill or let finish the blocking transaction identified by blocking_pid=4421 on postgres-primary, because it is causing lock_wait_ms=6032 for blocked_query_hash=cd77aa and is directly preventing payment initialization from completing.
  - Owner: `Database administrator`  |  Est. time: 15 min  |  Runbook: `postgres-blocking-transaction`

- [ ] **Step 2:** Review the slow insert on table=payment_transactions with slow_query_ms=8421 and query_hash=ab91ff, then compare execution plan and index usage to confirm whether the insert path is slow due to missing indexes or contention introduced by the current payment workload.
  - Owner: `Database administrator`  |  Est. time: 25 min  |  Runbook: `postgres-slow-insert-analysis`

- [ ] **Step 3:** Temporarily throttle payment-service write concurrency to the payments database so new payment attempts do not amplify lock waits while postgres-primary is already reporting transaction lock wait exceeded threshold and payment initialization failures.
  - Owner: `Service owner`  |  Est. time: 10 min  |  Runbook: `write-throttling`

- [ ] **Step 4:** Analyze postgres-primary logs around 2026-05-09T10:02:30Z-10:02:36Z to determine whether the slow queries and lock waits are caused by a hot row pattern in payment_transactions or by a recent application change in payment-service that changed the insert/update transaction pattern.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `postgres-contention-root-cause`


## DEPLOY_FAILURE — P2
**Services:** deployment-controller, payment-service, kubernetes

- [ ] **Step 1:** Roll back deployment=payment-service from version=v2.8.4 to previous_version=v2.8.3 in namespace=prod, because deployment-controller reports error rate increased after deployment and available_replicas=1 is far below desired_replicas=6.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-rollback`

- [ ] **Step 2:** Pause the current rollout or set maxUnavailable to 0 for payment-service so kubernetes does not continue replacing healthy replicas while only 1 of 6 desired replicas is available.
  - Owner: `Platform team`  |  Est. time: 10 min  |  Runbook: `deployment-freeze`

- [ ] **Step 3:** Verify whether the v2.8.4 change_id=CHG-9182 introduced the observed error-rate increase by comparing logs and metrics between v2.8.3 and v2.8.4, focusing on payment initialization, DB connection behavior, and pod crash frequency.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `release-regression-analysis`

- [ ] **Step 4:** After rollback or fix, watch payment-service availability in namespace=prod until available_replicas returns to 6 and error rate returns to baseline, then re-enable the rollout only if the regression cause is understood and mitigated.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `deployment-recovery`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
