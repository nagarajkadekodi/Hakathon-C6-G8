# Remediation Checklist — inc-bde77b9d
**Overall Severity:** P1  |  **Issues:** 5

---

## DB_TIMEOUT — P1
**Services:** payment-service, postgres-primary, api-gateway

- [ ] **Step 1:** On payment-service, immediately reduce pressure on postgres-primary by scaling out or temporarily throttling /api/v1/payments traffic at api-gateway while active_connections is at 195/200 and PostgreSQL is returning "remaining connection slots are reserved for non-replication superuser connections".
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `postgres-connection-slot-pressure`

- [ ] **Step 2:** Inspect payment-service JDBC/Hikari pool settings for the failing transaction path that logged error_code=DB_CONN_TIMEOUT and tune max pool size and connection timeout to prevent connection acquisition stalls; align the pool with postgres-primary max_connections=200 and current db=payments load.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `jdbc-pool-tuning`

- [ ] **Step 3:** Check postgres-primary for long-running transactions or blocked sessions in db=payments that are holding connections open, then terminate the worst offenders if they are safe to drop so the pool can recover from the wait_event=ClientRead saturation.
  - Owner: `Database administrator`  |  Est. time: 15 min  |  Runbook: `postgres-blocked-session-triage`

- [ ] **Step 4:** Review payment-service connection retry behavior around trace_id=a81d11 and ensure retries are bounded so failed DB attempts do not amplify pool exhaustion during the incident.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `retry-storm-mitigation`


## OOM_KILL — P1
**Services:** payment-service, kubelet, kubernetes

- [ ] **Step 1:** Immediately stabilize payment-service-7d9f84c9b6-rx2pm by increasing the pod memory limit/request above the current OOMKilled threshold and restarting the crashed container to stop the CrashLoopBackOff with Java heap space failures.
  - Owner: `Platform team`  |  Est. time: 10 min  |  Runbook: `k8s-memory-limit-bump`

- [ ] **Step 2:** Verify the JVM heap settings used by payment-service and reduce -Xmx if it is too close to the Kubernetes memory limit, because the pod logged java.lang.OutOfMemoryError: Java heap space before event=OOMKilled.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `jvm-heap-rightsize`

- [ ] **Step 3:** Inspect the payment-service-7d9f84c9b6-rx2pm pod for memory spikes, native memory usage, and any recent code path changes that correlate with restart_count=3 so you can determine whether the failure is heap pressure or a leak.
  - Owner: `Platform team`  |  Est. time: 25 min  |  Runbook: `pod-memory-profiling`

- [ ] **Step 4:** If the increased memory request is safe for cluster capacity, roll the payment-service deployment to a higher-memory replica set and confirm kubernetes no longer reports OOMKilled for namespace=prod pod=payment-service-7d9f84c9b6-rx2pm.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `deployment-memory-rollout`


## NETWORK_ERROR — P1
**Services:** api-gateway, payment-service

- [ ] **Step 1:** Reduce api-gateway timeout pressure on POST /api/v1/payments by temporarily increasing the upstream timeout beyond the observed 12030ms and 15012ms failures only if payment-service is already recovering; otherwise keep retries minimal to avoid amplifying upstream load.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-timeout-tuning`

- [ ] **Step 2:** Check whether the upstream payment-service pod behind api-gateway is still crash looping or slow from the OOM_KILL and DB_TIMEOUT conditions, because the gateway logged upstream=payment-service with both 504 upstream request timeout and 502 bad gateway from upstream.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `upstream-health-correlation`

- [ ] **Step 3:** Validate api-gateway retry policy for trace_id=e19bc1 and the POST /api/v1/payments route so request timeout after retry attempt does not create duplicate load or mask the real upstream latency problem.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `gateway-retry-policy`

- [ ] **Step 4:** After payment-service stabilizes, confirm gateway error rates fall below threshold by checking that status=504 and status=502 responses for upstream=payment-service stop recurring across the payment route.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `gateway-error-rate-validation`


## AUTH_ERROR — P1
**Services:** auth-service, redis-cache, api-gateway

- [ ] **Step 1:** Investigate redis-prod-01 latency immediately and clear saturation on the Redis session key path, since command GET key=session:98281 already showed latency_ms=2740 and auth-service is failing TOKEN_VALIDATION_FAILED with Redis session lookup timeout.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `redis-latency-triage`

- [ ] **Step 2:** Check redis-cache instance redis-prod-01 for slow commands, memory pressure, or network jitter, then restart or fail over the instance only if it is unhealthy and causing persistent session lookup timeouts.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `redis-failover-recovery`

- [ ] **Step 3:** Verify auth-service token validation timeouts and ensure the API gateway is not retrying auth requests excessively, because the gateway already returned status=401 with message="authentication failed due to token validation timeout" for trace_id=c91f12.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `auth-timeout-control`

- [ ] **Step 4:** Confirm session cache capacity and TTL settings for Redis-backed auth sessions so repeated GET session:* requests do not exceed the latency threshold that caused the user_id=20311 validation failure.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `redis-session-sizing`


## DEPLOY_FAILURE — P2
**Services:** deployment-controller, payment-service, kubernetes

- [ ] **Step 1:** Roll back payment-service from version=v2.8.4 to previous_version=v2.8.3 because deployment-controller detected increased error rate after deployment and kubernetes shows available_replicas=1 while desired_replicas=6.
  - Owner: `Platform team`  |  Est. time: 15 min  |  Runbook: `deployment-rollback`

- [ ] **Step 2:** Pause further rollout of change_id=CHG-9182 in namespace=prod until the payment-service error rate and replica availability recover, to prevent the degraded deployment from replacing healthy pods.
  - Owner: `Deployment controller`  |  Est. time: 10 min  |  Runbook: `rollout-pause`

- [ ] **Step 3:** Compare v2.8.4 against v2.8.3 for configuration, resource, and code changes that could explain the reduced availability and elevated errors in payment-service, focusing on anything that could also contribute to the DB_TIMEOUT and OOM_KILL symptoms.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `deployment-diff-analysis`

- [ ] **Step 4:** After rollback, verify kubernetes reports available_replicas returning to 6/6 and confirm the deployment-controller no longer logs "error rate increased after deployment" for payment-service.
  - Owner: `On-call engineer`  |  Est. time: 15 min  |  Runbook: `post-rollback-verification`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
