# Remediation Checklist — inc-ea7e1968
**Overall Severity:** P1  |  **Issues:** 6

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Relieve immediate pressure on postgres-primary by reducing active connections from 195/200: temporarily scale down payment-service traffic at api-gateway or pause non-essential payment transaction traffic until connection slots recover, because logs show "connection pool near exhaustion" and PostgreSQL is returning "remaining connection slots are reserved" errors.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-pressure-mitigation`

- [ ] **Step 2:** Increase PostgreSQL capacity headroom on postgres-primary by raising max_connections only if memory allows, and restart the pooler/database in a controlled window if the connection limit is already saturated; verify db=payments no longer reports wait_event=ClientRead at 195 active connections.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-max-connections-tuning`

- [ ] **Step 3:** Identify and terminate the blocking backend work causing lock waits on db=payments: inspect blocking_pid=4421 for the transaction behind query_hash=cd77aa, then kill or rollback the blocker if it is holding payment_transactions locks and contributing to the 6032 ms lock wait.
  - Owner: `Database administrator`  |  Est. time: 15 min  |  Runbook: `postgres-lock-contention-remediation`

- [ ] **Step 4:** Review the slow insert on table=payment_transactions for query_hash=ab91ff (slow_query_ms=8421) and add the needed index or adjust the insert path so the payment-service transaction creation no longer stalls under load.
  - Owner: `Service owner`  |  Est. time: 45 min  |  Runbook: `postgres-slow-insert-optimization`

- [ ] **Step 5:** Tune payment-service database pool settings so it stops exhausting postgres-primary slots: reduce per-pod pool size and enable backoff/retry limits for DB_CONN_TIMEOUT paths, then confirm api-gateway POST /api/v1/payments latency drops below timeout thresholds.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `db-pool-tuning`

- [ ] **Step 6:** Validate recovery by checking that postgres-primary active_connections falls well below 195, the "remaining connection slots" error stops appearing, and payment-service trace_id=a81d11 style DB_CONN_TIMEOUT events cease in the next log window.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-recovery-validation`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Stabilize the crashing pod payment-service-7d9f84c9b6-rx2pm in namespace=prod by scaling payment-service replicas above 1/6 only after the memory footprint is addressed, or temporarily reduce traffic routed to the crashing pod so CrashLoopBackOff does not continue to amplify failures.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-crashloop-stabilization`

- [ ] **Step 2:** Increase the Kubernetes memory limit for container=payment-service in deployment payment-service to exceed the observed Java heap demand, since kubelet reports OOMKilled and the app throws java.lang.OutOfMemoryError: Java heap space.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `k8s-memory-limit-adjustment`

- [ ] **Step 3:** Tune the JVM heap settings for payment-service so the process fits inside the container limit: set explicit -Xms/-Xmx values below the pod memory limit and verify the container no longer exceeds the memory ceiling during payment transaction handling.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `jvm-heap-sizing`

- [ ] **Step 4:** Inspect recent payment-service memory allocations and request spikes tied to order/payment processing, then fix the leak or high-retention code path that is driving heap exhaustion and repeated restarts_count=3.
  - Owner: `Service owner`  |  Est. time: 60 min  |  Runbook: `java-memory-leak-investigation`

- [ ] **Step 5:** After redeploying the corrected container config, confirm kubelet no longer emits Back-off restarting failed container for payment-service-7d9f84c9b6-rx2pm and that namespace=prod events stop showing OOMKilled.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `k8s-oom-recovery`

- [ ] **Step 6:** Review the pod resource requests/limits for deployment payment-service and set request/limit values that match observed production usage so the workload can stay within Kubernetes memory policy without repeated evictions.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `k8s-resource-rightsizing`


## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Address the immediate backend contention on postgres-primary by pausing non-critical writes to db=payments while slow_query_ms=8421 and lock_wait_ms=6032 conditions persist, to prevent further queue buildup on payment_transactions.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-contention-mitigation`

- [ ] **Step 2:** Investigate and resolve the lock chain behind blocking_pid=4421 for blocked_query_hash=cd77aa, since the log explicitly shows a transaction lock wait exceeded threshold on the payments database.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-lock-chain-analysis`

- [ ] **Step 3:** Optimize the slow insert on table=payment_transactions for query_hash=ab91ff by checking missing indexes, trigger overhead, and contention on the write path; implement the specific index or query rewrite needed for the 8421 ms insert.
  - Owner: `Database administrator`  |  Est. time: 50 min  |  Runbook: `postgres-write-path-optimization`

- [ ] **Step 4:** Reduce connection pressure on postgres-primary by lowering payment-service concurrency or pool size, because the evidence shows active_connections=195 max_connections=200 and the database is already near exhaustion while slow queries are piling up.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `db-connection-throttling`

- [ ] **Step 5:** Verify the fix by confirming lock_wait_ms drops below threshold, slow insert alerts for query_hash=ab91ff stop, and postgres-primary no longer reports connection pool near exhaustion for db=payments.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-performance-validation`


## NETWORK_ERROR — P1
**Services:** api-gateway, payment-service

- [ ] **Step 1:** Reduce immediate user impact by switching api-gateway routing for POST /api/v1/payments away from the unhealthy upstream payment-service instance if health checks show repeated 504/502 responses, to stop sending traffic into the timeout path.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-upstream-reroute`

- [ ] **Step 2:** Verify payment-service pod health and readiness behind api-gateway, because the gateway logs show upstream=payment-service with latency_ms=12030, 8321, and 15012; remove any pod that is not responding within the gateway timeout window.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `service-readiness-triage`

- [ ] **Step 3:** Increase or align api-gateway upstream timeout and retry policy only after confirming payment-service can complete requests, since the current retries still end in 504 and "request timeout after retry attempt" for path=/api/v1/payments.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `gateway-timeout-tuning`

- [ ] **Step 4:** Correlate the gateway failures with the payment-service DB_CONN_TIMEOUT and OOMKilled events from the same timestamps to confirm whether the 502/504s are downstream saturation rather than a network path defect.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `cross-service-failure-correlation`

- [ ] **Step 5:** After the downstream service is stabilized, validate api-gateway POST /api/v1/payments returns below timeout thresholds and that 502/504 rates drop to baseline across trace_ids a81d11, b12c44, and e19bc1.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-recovery-validation`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Reduce login/session impact by temporarily increasing auth-service tolerance for Redis lookup latency only if safe, or short-circuiting non-critical profile requests while redis-cache GET latency_ms=2740 is causing TOKEN_VALIDATION_FAILED timeouts.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `auth-failure-mitigation`

- [ ] **Step 2:** Inspect redis-prod-01 for the slow session key path session:98281 and determine whether the Redis node is under CPU, memory, or network saturation causing GET latency above threshold.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-slow-command-investigation`

- [ ] **Step 3:** Scale or replace the redis-cache instance if necessary and ensure auth-service can complete token validation without Redis session lookup timeout, because the evidence shows repeated 401s on /api/v1/profile through api-gateway.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `redis-capacity-remediation`

- [ ] **Step 4:** Check auth-service token validation code for excessive synchronous Redis calls or missing caching of session data, then reduce the number of Redis GETs per request to avoid latency amplification.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `auth-redis-optimization`

- [ ] **Step 5:** Validate recovery by confirming redis-prod-01 GET latency returns to normal, auth-service stops emitting TOKEN_VALIDATION_FAILED reason="Redis session lookup timeout", and api-gateway profile requests stop returning 401 due to timeout.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `auth-recovery-validation`


## DEPLOY_FAILURE — P1
**Services:** deployment-controller, payment-service, kubernetes

- [ ] **Step 1:** Roll back payment-service from version=v2.8.4 to previous_version=v2.8.3 in namespace=prod, because deployment-controller reports error rate increased after deployment and kubernetes shows available_replicas=1 desired_replicas=6.
  - Owner: `Release engineer`  |  Est. time: 10 min  |  Runbook: `k8s-deployment-rollback`

- [ ] **Step 2:** Pause further rollout of change_id=CHG-9182 and hold the payment-service deployment at the last known good revision until availability returns to the desired 6 replicas.
  - Owner: `Release engineer`  |  Est. time: 5 min  |  Runbook: `deploy-freeze`

- [ ] **Step 3:** Compare v2.8.4 against v2.8.3 for changes affecting payment transaction flow, DB connection usage, and memory behavior, since the same service is already experiencing DB_CONN_TIMEOUT and OOMKilled signals.
  - Owner: `Service owner`  |  Est. time: 45 min  |  Runbook: `deployment-regression-analysis`

- [ ] **Step 4:** Redeploy payment-service only after the rollback is confirmed healthy, using a canary or one-replica progressive rollout to catch the error-rate increase before it impacts all 6 desired replicas again.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `canary-deploy-payment-service`

- [ ] **Step 5:** Validate that deployment=payment-service reaches available_replicas=6 desired_replicas=6 and that deployment-controller no longer reports a post-deploy error-rate increase for version=v2.8.4 or the candidate replacement.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `deployment-recovery-validation`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
