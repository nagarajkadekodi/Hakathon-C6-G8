# Remediation Checklist — inc-a26a8228
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Reduce immediate pressure on `postgres-primary` for the `payments` database by pausing or scaling down non-essential `payment-service` traffic, because logs show `active_connections=195 max_connections=200` and `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-slot-protection`

- [ ] **Step 2:** Rollback `payment-service` from `v2.8.4` to `v2.8.3` as recommended by `incident-detector` (`incident_id=INC-20260509-001`, `recommended_action="rollback payment-service to v2.8.3..."`) to stop the release from amplifying DB connection usage.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-service-rollback`

- [ ] **Step 3:** Increase the `payment-service` PostgreSQL pool size conservatively and enforce connection limits/timeouts so it stops saturating `postgres-primary`; verify the pool change against the `DB_CONN_TIMEOUT` errors on trace `a81d11` and the near-exhaustion warning on `payments`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `pg-pool-tuning`

- [ ] **Step 4:** Inspect and clear the long-running lock on `postgres-primary` causing `lock_wait_ms=6032` with `blocking_pid=4421` and the slow insert on `table=payment_transactions` (`query_hash=ab91ff`) so payment inserts can proceed normally.
  - Owner: `Database engineer`  |  Est. time: 30 min  |  Runbook: `postgres-lock-wait-triage`

- [ ] **Step 5:** Restart unhealthy `payment-service` pods only after the rollback and DB pressure reduction are in place, because the same service is emitting repeated `DB_CONN_TIMEOUT` failures and may be holding stale connections.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `restart-unhealthy-payment-pods`

- [ ] **Step 6:** Review query plans and transaction patterns for `payment_transactions` insert path associated with `query_hash=ab91ff` and correlate to the pool exhaustion window to identify whether indexing or transaction scope changes are needed as the root cause fix.
  - Owner: `Database engineer`  |  Est. time: 45 min  |  Runbook: `slow-query-root-cause-analysis`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Immediately stabilize `payment-service-7d9f84c9b6-rx2pm` in namespace `prod` by restarting the crash-looping pod only after capturing current state, since kubelet reports `restart_count=3`, `CrashLoopBackOff`, and Kubernetes reports `OOMKilled`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-oom-recovery`

- [ ] **Step 2:** Raise the Kubernetes memory limit for `payment-service` above the current value that is producing `message="Container killed due to memory limit exceeded"`, then redeploy the pod to prevent immediate repeat OOM kills.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-memory-limit-adjustment`

- [ ] **Step 3:** Reduce Java heap pressure for `payment-service` by setting heap flags to fit within the pod limit, because the application is throwing `java.lang.OutOfMemoryError message="Java heap space"` before Kubernetes kills it.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `java-heap-tuning`

- [ ] **Step 4:** Verify whether the recent `v2.8.4` deployment changed memory behavior by comparing pod memory usage and restart patterns for `payment-service-7d9f84c9b6-rx2pm` before and after rollout.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `deployment-memory-regression-check`

- [ ] **Step 5:** Inspect application logs and heap behavior for the OOM event around `2026-05-09T10:01:22.553Z` to determine whether an application leak, oversized cache, or request spike is driving the `Java heap space` failure.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `heap-dump-analysis`


## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Treat the DB issue as an active incident and execute the recommended `rollback payment-service to v2.8.3` from `incident_id=INC-20260509-001`, since `payment-service` is already showing degraded transaction handling and the detector flags rollback as the immediate mitigation.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-service-rollback`

- [ ] **Step 2:** Address the `postgres-primary` slow insert on `table=payment_transactions` (`slow_query_ms=8421`, `query_hash=ab91ff`) by checking the execution plan and applying the minimal fix needed to reduce insert latency.
  - Owner: `Database engineer`  |  Est. time: 35 min  |  Runbook: `postgres-slow-insert-triage`

- [ ] **Step 3:** Resolve the `lock_wait_ms=6032` condition by identifying the blocking transaction at `blocking_pid=4421` for `blocked_query_hash=cd77aa` and clearing or rescheduling the conflicting transaction.
  - Owner: `Database engineer`  |  Est. time: 25 min  |  Runbook: `postgres-lock-resolution`

- [ ] **Step 4:** Increase the `payment-service` DB connection pool only after the DB lock and slow query are addressed, to prevent compounding the `active_connections=195 max_connections=200` pressure already seen on `postgres-primary`.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `pg-pool-exhaustion`

- [ ] **Step 5:** Restart any `payment-service` pods that were left unhealthy after the transaction delays, using the rollout state after rollback to ensure the service comes back on `v2.8.3` with normal DB behavior.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `restart-payment-after-db-fix`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Reduce immediate auth failures by checking `redis-prod-01` health and relieving load on the session cache, because `GET key=session:98281` is taking `latency_ms=2740` and `auth-service` is returning `TOKEN_VALIDATION_FAILED reason="Redis session lookup timeout" status=401`.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `redis-session-timeout-mitigation`

- [ ] **Step 2:** Restart or reschedule the `redis-cache` instance `redis-prod-01` if it is degraded, then verify session lookup latency drops below the threshold before re-enabling full token validation traffic.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `redis-restart-healthcheck`

- [ ] **Step 3:** Inspect `auth-service` token validation path for any unnecessary Redis calls tied to `user_id=20311` and ensure cached session reads do not block request processing during Redis slowness.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `auth-token-cache-tuning`

- [ ] **Step 4:** Verify `api-gateway` retries and timeout settings for upstream `auth-service` because `/api/v1/profile` is returning `status=401 latency_ms=3102` due to token validation timeouts.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `gateway-auth-timeout-config`

- [ ] **Step 5:** Investigate why Redis session commands are hitting `latency_ms=2740` on `redis-prod-01` to determine whether the issue is CPU saturation, memory pressure, or an overloaded keyspace for `session:*` entries.
  - Owner: `Database engineer`  |  Est. time: 45 min  |  Runbook: `redis-latency-root-cause`


## DEPLOY_FAILURE — P1
**Services:** payment-service, deployment-controller, kubernetes

- [ ] **Step 1:** Rollback `payment-service` from `version=v2.8.4` to `previous_version=v2.8.3` immediately, because `deployment-controller` reports `error rate increased after deployment` and Kubernetes shows `available_replicas=1 desired_replicas=6`.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-service-rollback`

- [ ] **Step 2:** Pause further rollout of `payment-service` in namespace `prod` until replica availability recovers, since the current deployment is below threshold and is reducing production capacity to 1 of 6 replicas.
  - Owner: `Platform team`  |  Est. time: 5 min  |  Runbook: `pause-k8s-rollout`

- [ ] **Step 3:** Check the rollout and pod health for `change_id=CHG-9182` to identify whether the new `v2.8.4` image, configuration, or environment change caused the post-deployment error spike.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `deployment-regression-triage`

- [ ] **Step 4:** Restore service capacity by ensuring `payment-service` returns to 6 desired replicas after the rollback and confirming all pods become available before resuming traffic.
  - Owner: `On-call engineer`  |  Est. time: 20 min  |  Runbook: `restore-deployment-capacity`

- [ ] **Step 5:** Perform a post-rollback comparison of `v2.8.4` versus `v2.8.3` to determine which change introduced the elevated error rate and reduced availability in production.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `release-diff-analysis`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
