# Remediation Checklist — inc-a0fd00db
**Overall Severity:** P1  |  **Issues:** 4

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** Reduce load on postgres-primary by temporarily throttling payment-service write traffic through api-gateway for payment transaction endpoints while the database is near exhaustion (active_connections=195/200 and "remaining connection slots are reserved for non-replication superuser connections").
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-pressure-mitigation`

- [ ] **Step 2:** Increase postgres-primary connection capacity if headroom allows by checking current max_connections=200 and, if safe for memory, raising it modestly while verifying PostgreSQL can sustain the additional backend processes without OOM pressure.
  - Owner: `Database administrator`  |  Est. time: 20 min  |  Runbook: `postgres-max-connections-tuning`

- [ ] **Step 3:** Inspect payment-service connection pool settings for exhaustion triggers and lower pool size to stay below postgres-primary capacity, then restart payment-service pods to pick up the updated pool configuration after confirming the DB_CONN_TIMEOUT errors on trace_id=a81d11 are reduced.
  - Owner: `Service owner`  |  Est. time: 25 min  |  Runbook: `app-db-pool-tuning`

- [ ] **Step 4:** Investigate postgres-primary latency and wait_event=ClientRead around 2026-05-09T10:01:13Z by checking slow queries, long-lived transactions, and idle-in-transaction sessions in db=payments to identify why the pool is saturating.
  - Owner: `Database administrator`  |  Est. time: 30 min  |  Runbook: `postgres-slow-transaction-investigation`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Immediately stop the CrashLoopBackOff on payment-service-7d9f84c9b6-rx2pm by patching the deployment to raise the container memory limit above the current level that is triggering OOMKilled and Java heap space errors, then restart the pod in namespace=prod.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-oom-limit-bump`

- [ ] **Step 2:** Reduce the Java heap to fit within the Kubernetes memory limit for payment-service if the current JVM max heap is too close to the container cap, because the pod is repeatedly failing with java.lang.OutOfMemoryError: Java heap space before kubelet reports OOMKilled.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `jvm-heap-vs-container-memory`

- [ ] **Step 3:** Verify whether the deployment of payment-service v2.8.4 increased memory usage by comparing it with the prior stable version and reviewing any recent code paths that allocate large objects during payment processing.
  - Owner: `Application engineer`  |  Est. time: 30 min  |  Runbook: `release-memory-regression-check`

- [ ] **Step 4:** Check pod metrics and Kubernetes events for payment-service-7d9f84c9b6-rx2pm to confirm restart_count=3 and correlate memory spikes with traffic or specific requests before deciding whether to keep the higher memory limit permanently.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `k8s-pod-memory-forensics`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Mitigate user-facing 401s by reducing auth-service dependency on slow Redis lookups for token validation, such as enabling a short-lived fallback cache for session: lookups while redis-cache instance redis-prod-01 is returning GET latency_ms=2740.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `redis-session-lookup-mitigation`

- [ ] **Step 2:** Investigate redis-prod-01 saturation and the high latency on command GET key=session:98281 by checking CPU, memory, eviction, and network latency on redis-cache before the auth-service timeout at 2026-05-09T10:02:05Z.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-latency-investigation`

- [ ] **Step 3:** Temporarily scale out or replace the redis-cache tier if the current instance cannot meet token-validation latency, ensuring auth-service can resolve session lookups without causing api-gateway 401s on /api/v1/profile.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `redis-capacity-scale-out`

- [ ] **Step 4:** Review auth-service token validation timeout settings and Redis client timeouts to ensure they are aligned with expected session lookup latency, then validate the fix against trace_id=c91f12 and similar failures.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `auth-redis-timeout-tuning`


## DEPLOY_FAILURE — P1
**Services:** payment-service, deployment-controller, kubernetes, api-gateway

- [ ] **Step 1:** Roll back payment-service from v2.8.4 to previous_version=v2.8.3 in namespace=prod because the deployment controller reports error rate increased after deployment and available_replicas dropped to 1 of 6.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `k8s-deployment-rollback`

- [ ] **Step 2:** Pause the rollout for deployment=payment-service and prevent further promotion of version=v2.8.4 until the availability issue is resolved, since change_id=CHG-9182 correlates with the replica drop and degraded error rate.
  - Owner: `Release manager`  |  Est. time: 5 min  |  Runbook: `deployment-rollout-freeze`

- [ ] **Step 3:** Verify the health of payment-service pods after rollback by confirming available_replicas return toward desired_replicas=6 and that api-gateway error rates normalize for payment traffic.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `post-rollback-health-check`

- [ ] **Step 4:** Perform a release diff between v2.8.3 and v2.8.4 to identify the specific change causing reduced availability, then add a targeted pre-prod validation for the failing behavior before redeploying.
  - Owner: `Service owner`  |  Est. time: 40 min  |  Runbook: `deployment-regression-analysis`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
