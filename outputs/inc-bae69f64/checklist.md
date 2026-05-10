# Remediation Checklist — inc-bae69f64
**Overall Severity:** P0  |  **Issues:** 3

---

## OOM_KILL — P0
**Services:** payment-service, kubelet

- [ ] **Step 1:** Immediately increase the memory limit for payment-service from 512Mi to 1024Mi by patching the deployment: `kubectl set resources deployment/payment-service -c payment-service --limits=memory=1024Mi --requests=memory=768Mi -n <namespace>`. This will trigger a rolling restart and break the CrashLoopBackOff cycle on pod payment-service-7d9f8b-xk2p9.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-oom-memory-limit-bump`

- [ ] **Step 2:** Verify the new payment-service pods reach Running state and that OOMKilled events cease: `kubectl get pods -l app=payment-service -w` and `kubectl describe pod -l app=payment-service | grep -E 'OOMKilled|Restart|State'`. Confirm restart count is no longer incrementing.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-pod-health-verify`

- [ ] **Step 3:** Validate payment processing is functional end-to-end by running a synthetic transaction through the payment-service API. Check for any in-flight transactions that may have been left in an inconsistent state during the 3+ OOMKilled restarts and coordinate with the payments team to audit and reconcile those records.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `payment-transaction-reconciliation`

- [ ] **Step 4:** Alert the on-call escalation chain (P0 bridge) that payment-service was fully unavailable due to CrashLoopBackOff with 3+ restarts starting at 2026-05-09T07:46:23Z. Capture the incident window for SLA reporting.
  - Owner: `Incident commander`  |  Est. time: 5 min  |  Runbook: `p0-escalation-notification`

- [ ] **Step 5:** Pull memory usage metrics from Prometheus/Grafana for payment-service for the 24 hours preceding 07:46:23Z. Identify whether the 512Mi limit breach was due to a gradual memory leak, a traffic spike, or a recent code change. Run `kubectl top pod -l app=payment-service` and cross-reference with HPA and request-rate metrics.
  - Owner: `Platform team`  |  Est. time: 20 min  |  Runbook: `k8s-oom-memory-profiling`

- [ ] **Step 6:** If memory growth is determined to be a leak (gradual increase trend), schedule heap profiling for payment-service in the next deployment window. If it is traffic-driven, evaluate adding a HorizontalPodAutoscaler targeting 70% memory utilization and set a permanent memory limit of 1024Mi with a request of 768Mi after load-testing validates this headroom.
  - Owner: `Service owner`  |  Est. time: 30 min  |  Runbook: `k8s-oom-root-cause-remediation`


## DB_TIMEOUT — P1
**Services:** order-service, api-gateway

- [ ] **Step 1:** Immediately increase the PostgreSQL connection pool size for order-service from max=20 to max=50 via environment variable or config map update (e.g., `DB_POOL_MAX=50`), then perform a rolling restart: `kubectl rollout restart deployment/order-service`. This directly addresses the pool exhaustion state (20/20 active, 47 waiting) seen at 07:47:12Z.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `pg-pool-exhaustion-bump`

- [ ] **Step 2:** Validate PostgreSQL server can sustain the increased pool size. Check current max_connections on the RDS/PostgreSQL instance: `SELECT count(*), state FROM pg_stat_activity GROUP BY state;`. Ensure server-side max_connections (typically 100-500) minus connections from other services leaves sufficient headroom for order-service pool=50.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `pg-server-connection-capacity-check`

- [ ] **Step 3:** Manually reset the api-gateway circuit breaker for the order-service upstream if it does not auto-close after order-service recovers. Confirm via api-gateway admin endpoint or config that the circuit breaker is CLOSED and upstream order-service is returning 2xx. Check api-gateway logs for '500' rates dropping to zero.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `api-gateway-circuit-breaker-reset`

- [ ] **Step 4:** Monitor order-service pool metrics post-restart to confirm the waiting queue (previously 47) has cleared and connection acquisition no longer times out after 5000ms. Use `kubectl logs -l app=order-service --since=5m | grep -E 'pool|timeout|connection'` and application-level pool metrics dashboards.
  - Owner: `On-call engineer`  |  Est. time: 10 min  |  Runbook: `pg-pool-queue-drain-verify`

- [ ] **Step 5:** Investigate what caused pool exhaustion at 07:47:12Z. Check order-service request throughput, slow query logs on PostgreSQL (queries exceeding 1s holding connections), and whether any long-running transactions or deadlocks were present. Run: `SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 20;`
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `pg-slow-query-investigation`

- [ ] **Step 6:** Implement connection pool right-sizing and safeguards for order-service: set a connection acquisition timeout alert at 80% pool utilization (16/20), add PgBouncer as a connection pooler if the PostgreSQL server cannot sustain higher direct connections, and configure the order-service to return a 503 with retry-after header rather than propagating a 500 to api-gateway when the pool is saturated.
  - Owner: `Platform team`  |  Est. time: 60 min  |  Runbook: `pg-pool-long-term-hardening`


## DEPLOY_FAILURE — P2
**Services:** notification-service, kubelet

- [ ] **Step 1:** Verify whether the image `registry.prod.internal/notification-service:v1.2.3` exists in the internal registry. Run: `docker manifest inspect registry.prod.internal/notification-service:v1.2.3` or query the registry API. If the tag is missing, determine the correct existing tag (e.g., v1.2.2 or latest) and identify who triggered the v1.2.3 deployment.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `registry-image-tag-verify`

- [ ] **Step 2:** If image v1.2.3 was never published, immediately roll back the notification-service deployment to the last known good image tag: `kubectl rollout undo deployment/notification-service`. Confirm pods exit ImagePullBackOff and reach Running state: `kubectl rollout status deployment/notification-service`.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-deploy-rollback`

- [ ] **Step 3:** If image v1.2.3 was built but not pushed to `registry.prod.internal`, locate the artifact in the CI/CD pipeline (e.g., Jenkins/GitHub Actions build for notification-service:v1.2.3), re-push it to `registry.prod.internal/notification-service:v1.2.3`, then re-apply the deployment: `kubectl rollout restart deployment/notification-service`.
  - Owner: `Service owner`  |  Est. time: 15 min  |  Runbook: `registry-image-republish`

- [ ] **Step 4:** Verify the notification-service pod exits ImagePullBackOff and reaches Running: `kubectl get pod -l app=notification-service -w`. Confirm no ErrImagePull events remain: `kubectl describe pod -l app=notification-service | grep -E 'ErrImagePull|ImagePullBackOff|Started'`.
  - Owner: `On-call engineer`  |  Est. time: 5 min  |  Runbook: `k8s-pod-imagepull-verify`

- [ ] **Step 5:** Assess notification delivery backlog accumulated since 07:48:05Z when the pod entered Pending. Determine whether missed notifications (e.g., order confirmations, alerts) need to be replayed from a queue (Kafka/SQS topic) or if they are permanently lost. Coordinate with the service owner on user communication if notification gaps are user-visible.
  - Owner: `Service owner`  |  Est. time: 20 min  |  Runbook: `notification-backlog-replay`

- [ ] **Step 6:** Identify the root cause of the missing image: audit the CI/CD pipeline for the notification-service v1.2.3 release. Determine whether the image push step was skipped, the registry credentials expired, or the deployment manifest was updated before the build completed. Add a CI gate that validates image existence in `registry.prod.internal` before updating Kubernetes manifests to prevent recurrence.
  - Owner: `Platform team`  |  Est. time: 30 min  |  Runbook: `cicd-image-push-gate-enforcement`


---

## Post-Incident

- [ ] Confirm all services are stable and error rate is back to baseline
- [ ] Write post-mortem document within 48 hours
- [ ] Update runbooks with any new learnings
- [ ] Schedule blameless retrospective with team
