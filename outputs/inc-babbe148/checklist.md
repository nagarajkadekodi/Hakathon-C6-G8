# Remediation Checklist — inc-babbe148
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** On postgres-primary for db=payments, immediately relieve connection pressure by identifying long-lived sessions driving active_connections=195/200 and terminating nonessential sessions so reserved superuser slots remain available; evidence shows "connection pool near exhaustion" and "remaining connection slots are reserved".
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-pressure`

- [ ] **Step 2:** Reduce payment-service database concurrency in prod by lowering the app-side pool size and request concurrency until postgres-primary active_connections drops below the warning threshold, because payment-service is failing on DB_CONN_TIMEOUT while the primary is at 195 of 200 connections.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-service-db-throttle`

- [ ] **Step 3:** Inspect the slow insert on table payment_transactions (slow_query_ms=8421, query_hash=ab91ff) and the lock wait exceeded threshold (lock_wait_ms=6032, blocked_query_hash=cd77aa, blocking_pid=4421) on postgres-primary; remove or resolve the blocking transaction and confirm the insert path is no longer waiting on locks.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-lock-contention`

- [ ] **Step 4:** Validate payment-service transaction retry behavior for trace_id=a81d11 and order_id=ORD-78219, then reprocess a failed payment only after postgres-primary reports healthy connection headroom and no active lock waits.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-retry-validation`

- [ ] **Step 5:** Investigate whether the connection pool exhaustion is caused by the recent payment_transactions slow inserts and lock contention by reviewing postgres-primary query plans and transaction isolation settings for the payment write path.
  - Owner: `Database administrator`  |  Est. time: 30 min  |  Runbook: `postgres-query-plan-review`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Stabilize payment-service in namespace=prod by temporarily increasing the pod memory limit for payment-service-7d9f84c9b6-rx2pm or scaling the deployment to replace the crashing pod, because kubelet reports CrashLoopBackOff and Kubernetes event OOMKilled.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `k8s-memory-limit-increase`

- [ ] **Step 2:** Reduce JVM heap pressure in payment-service by setting the Java heap options below the container memory limit and restarting the workload, because the pod error is java.lang.OutOfMemoryError: "Java heap space".
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `java-heap-tuning`

- [ ] **Step 3:** Check the current resource requests/limits for deployment payment-service in prod and compare them with the crash pod payment-service-7d9f84c9b6-rx2pm to confirm whether the container memory limit is too low for peak transaction load.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `k8s-resource-review`

- [ ] **Step 4:** Review payment-service application logs and heap usage patterns around 2026-05-09T10:01:22.553Z to identify any memory growth tied to payment transaction handling, object retention, or unbounded caches before restoring full traffic.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `jvm-memory-leak-triage`


## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** On postgres-primary, address the blocking transaction identified by blocking_pid=4421 and unblock the payment_transactions write path, since lock_wait_ms=6032 and payment-service is failing with PAYMENT_INIT_FAILED.
  - Owner: `Database administrator`  |  Est. time: 15 min  |  Runbook: `postgres-blocking-transaction`

- [ ] **Step 2:** Reduce contention on table payment_transactions by pausing or rate-limiting the hottest payment writes from payment-service until slow_query_ms=8421 drops and new inserts stop timing out.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `payment-write-throttle`

- [ ] **Step 3:** Inspect the slow insert query_hash=ab91ff on postgres-primary and determine whether missing indexes, dead tuples, or trigger overhead are causing the 8421 ms insert latency.
  - Owner: `Database administrator`  |  Est. time: 30 min  |  Runbook: `postgres-slow-insert-analysis`

- [ ] **Step 4:** Retry the failed payment initialization for order_id=ORD-78223 only after postgres-primary reports no lock waits and payment-service can connect successfully without DB_CONN_TIMEOUT errors.
  - Owner: `Service owner`  |  Est. time: 10 min  |  Runbook: `payment-init-retry`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Restore Redis session lookup performance on redis-prod-01 by reducing latency for GET key=session:98281, because auth-service is failing token validation with reason="Redis session lookup timeout" and api-gateway is returning 401s.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `redis-latency-mitigation`

- [ ] **Step 2:** Inspect redis-cache saturation, slow commands, and network reachability from auth-service to redis-prod-01 to determine why command latency reached 2740 ms for session:98281.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-slow-command-triage`

- [ ] **Step 3:** Temporarily increase auth-service tolerance for Redis lookup latency or enable a short-lived fallback path for token validation so api-gateway requests to /api/v1/profile stop failing while Redis is recovered.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `auth-service-fallback-validation`

- [ ] **Step 4:** Verify end-to-end token validation for trace_id=c91f12 after redis-cache recovers, then confirm api-gateway returns 200 instead of 401 for GET /api/v1/profile.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `auth-end-to-end-check`


## DEPLOY_FAILURE — P2
**Services:** payment-service, deployment-controller, kubernetes

- [ ] **Step 1:** Roll back deployment payment-service version=v2.8.4 to previous_version=v2.8.3 in namespace=prod, because deployment-controller detected increased error rate after change_id=CHG-9182 and kubernetes reports only 1 of 6 replicas available.
  - Owner: `Release engineer`  |  Est. time: 10 min  |  Runbook: `deployment-rollback`

- [ ] **Step 2:** Pause further rollout of payment-service v2.8.4 and verify that the remaining healthy replica is serving traffic while availability is below threshold at available_replicas=1 desired_replicas=6.
  - Owner: `Platform team`  |  Est. time: 5 min  |  Runbook: `deployment-pause`

- [ ] **Step 3:** Compare logs and metrics between v2.8.3 and v2.8.4 for payment-service to identify the regression that caused the post-deploy error rate increase observed by deployment-controller.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `deployment-regression-analysis`

- [ ] **Step 4:** Only after rollback or fix validation, re-enable the payment-service deployment in prod and confirm kubernetes restores available_replicas to 6/6 without increased errors.
  - Owner: `Release engineer`  |  Est. time: 15 min  |  Runbook: `deployment-recovery-validation`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
