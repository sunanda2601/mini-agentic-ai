# Payment Service - High Error Rate

## Symptoms

- HTTP 500 errors
- Increased latency
- Database connection timeouts

## Investigation

1. Check payment-service logs.
2. Check payment-service metrics.
3. Check payment-db health.
4. Check recent deployment/version.

## Remediation

If payment-db is healthy:

- Restart payment-service.

Do not automatically restart payment-db.

## Safety

Restarting payment-service is allowed.

Restarting payment-db requires manual approval.