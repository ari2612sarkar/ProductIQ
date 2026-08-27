# METRICS.md

## Product Metrics Definitions

This document defines all product metrics used in the Autonomous Product Intelligence & Decision Engine.

---

## Core Metrics

### 1. Daily Active Users (DAU)

**Definition**: Number of unique users who performed at least one tracked event in a 24-hour period.

**Formula**: `COUNT(DISTINCT user_id) FROM events WHERE DATE(timestamp) = target_date`

**Required Tables**: `events`

**Time Window**: 24 hours (midnight to midnight UTC)

**Edge Cases**:
- Users with multiple sessions count once
- Events without user_id are excluded
- Timezone: UTC

**SQL Implementation**:
```sql
SELECT COUNT(DISTINCT user_id) as dau
FROM events
WHERE DATE(timestamp) = '2024-01-15';
```

---

### 2. Weekly Active Users (WAU)

**Definition**: Number of unique users who performed at least one tracked event in a 7-day period.

**Formula**: `COUNT(DISTINCT user_id) FROM events WHERE timestamp >= week_start AND timestamp < week_start + INTERVAL '7 days'`

**Required Tables**: `events`

**Time Window**: 7 days (Monday to Sunday or rolling 7-day window)

**Edge Cases**:
- Rolling WAU vs calendar week WAU
- Users active on boundary days

**SQL Implementation**:
```sql
SELECT COUNT(DISTINCT user_id) as wau
FROM events
WHERE timestamp >= '2024-01-08' AND timestamp < '2024-01-15';
```

---

### 3. Monthly Active Users (MAU)

**Definition**: Number of unique users who performed at least one tracked event in a 30-day period.

**Formula**: `COUNT(DISTINCT user_id) FROM events WHERE timestamp >= month_start AND timestamp < month_start + INTERVAL '30 days'`

**Required Tables**: `events`

**Time Window**: 30 days (rolling or calendar month)

**SQL Implementation**:
```sql
SELECT COUNT(DISTINCT user_id) as mau
FROM events
WHERE timestamp >= '2024-01-01' AND timestamp < '2024-01-31';
```

---

### 4. Activation Rate

**Definition**: Percentage of new users who complete the activation event within a defined time window.

**Formula**: `(COUNT(DISTINCT user_id WHERE activation_event) / COUNT(DISTINCT user_id WHERE signup)) * 100`

**Required Tables**: `users`, `events`

**Activation Events**: `onboarding_complete`, `first_value_event`, `first_purchase`

**Time Window**: Typically 7 or 30 days post-signup

**Edge Cases**:
- Users who activate without explicit signup event
- Multiple activation events per user

**SQL Implementation**:
```sql
WITH signups AS (
  SELECT id, created_at
  FROM users
  WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01'
),
activations AS (
  SELECT DISTINCT user_id
  FROM events
  WHERE event_name IN ('onboarding_complete', 'first_value_event')
    AND timestamp >= '2024-01-01'
    AND timestamp < '2024-02-01'
)
SELECT
  COUNT(DISTINCT a.user_id)::float / COUNT(DISTINCT s.id) * 100 as activation_rate
FROM signups s
LEFT JOIN activations a ON s.id = a.user_id;
```

---

### 5. Conversion Rate

**Definition**: Percentage of users who complete a target conversion event.

**Formula**: `(COUNT(DISTINCT user_id WHERE conversion_event) / COUNT(DISTINCT user_id WHERE eligible)) * 100`

**Required Tables**: `users`, `events`, `subscriptions`

**Conversion Events**: `purchase`, `trial_start`, `subscription_start`

**Eligible Population**: Free users, trial users, or all users depending on context

**SQL Implementation**:
```sql
WITH eligible AS (
  SELECT DISTINCT user_id
  FROM users
  WHERE status = 'active' AND plan_id = (SELECT id FROM plans WHERE name = 'Free')
),
converted AS (
  SELECT DISTINCT user_id
  FROM events
  WHERE event_name = 'purchase'
    AND timestamp >= '2024-01-01'
)
SELECT COUNT(DISTINCT c.user_id)::float / COUNT(DISTINCT e.user_id) * 100 as conversion_rate
FROM eligible e
LEFT JOIN converted c ON e.user_id = c.user_id;
```

---

### 6. Retention Rate

**Definition**: Percentage of users from a cohort who remain active after N days.

**Formula**: `(COUNT(DISTINCT user_id active on day N) / COUNT(DISTINCT user_id in cohort)) * 100`

**Required Tables**: `users`, `events`

**Cohort Definition**: Users who signed up in the same time period (day, week, month)

**N-Day Retention**: Typically D1, D7, D30

**Edge Cases**:
- Users who churn and return
- Definition of "active" (any event vs specific events)

**SQL Implementation**:
```sql
WITH cohorts AS (
  SELECT user_id, DATE_TRUNC('day', created_at) as cohort_date
  FROM users
  WHERE created_at >= '2024-01-01'
),
activity AS (
  SELECT DISTINCT e.user_id, DATE_TRUNC('day', e.timestamp) as activity_date
  FROM events e
  JOIN cohorts c ON e.user_id = c.user_id
  WHERE e.timestamp >= c.cohort_date
)
SELECT
  c.cohort_date,
  COUNT(DISTINCT a.user_id)::float / COUNT(DISTINCT c.user_id) * 100 as retention_rate
FROM cohorts c
LEFT JOIN activity a ON c.user_id = a.user_id AND a.activity_date = c.cohort_date + INTERVAL '30 days'
GROUP BY c.cohort_date;
```

---

### 7. Churn Rate

**Definition**: Percentage of users who cancel or stop using the product in a given period.

**Formula**: `(COUNT(DISTINCT user_id churned) / COUNT(DISTINCT user_id active at period start)) * 100`

**Required Tables**: `subscriptions`, `users`

**Churn Definitions**:
- Voluntary: User-initiated cancellation
- Involuntary: Payment failure, card expired
- Definition: Subscription status = 'cancelled' or 'expired'

**Time Window**: Monthly or quarterly

**SQL Implementation**:
```sql
WITH active_start AS (
  SELECT DISTINCT user_id
  FROM subscriptions
  WHERE status = 'active'
    AND current_period_start <= '2024-01-01'
    AND current_period_end > '2024-01-01'
),
churned AS (
  SELECT DISTINCT user_id
  FROM subscriptions
  WHERE status IN ('cancelled', 'expired')
    AND cancelled_at >= '2024-01-01'
    AND cancelled_at < '2024-02-01'
)
SELECT COUNT(DISTINCT c.user_id)::float / COUNT(DISTINCT a.user_id) * 100 as churn_rate
FROM active_start a
LEFT JOIN churned c ON a.user_id = c.user_id;
```

---

### 8. ARPU (Average Revenue Per User)

**Definition**: Total revenue divided by number of active users.

**Formula**: `SUM(revenue) / COUNT(DISTINCT active_user_id)`

**Required Tables**: `payments`, `subscriptions`, `users`

**Time Window**: Monthly (MRR/ARPU) or annual (ARPU)

**Edge Cases**:
- Only count successful payments
- Handle refunds (subtract)
- Include recurring vs one-time revenue

**SQL Implementation**:
```sql
WITH revenue AS (
  SELECT SUM(amount) as total_revenue
  FROM payments
  WHERE status = 'succeeded'
    AND paid_at >= '2024-01-01'
    AND paid_at < '2024-02-01'
),
active_users AS (
  SELECT COUNT(DISTINCT user_id) as user_count
  FROM users
  WHERE status = 'active'
    AND created_at < '2024-02-01'
)
SELECT total_revenue / user_count as arpu
FROM revenue, active_users;
```

---

### 9. Revenue (MRR/ARR)

**Definition**: Monthly Recurring Revenue (MRR) and Annual Recurring Revenue (ARR).

**MRR Formula**: `SUM(monthly_recurring_charge) for all active subscriptions`

**ARR Formula**: `MRR * 12`

**Required Tables**: `subscriptions`, `plans`, `payments`

**Edge Cases**:
- Annual plans: divide by 12 for MRR
- Trial subscriptions: exclude
- Paused subscriptions: exclude
- Prorated charges: handle appropriately

**SQL Implementation**:
```sql
SELECT
  SUM(CASE
    WHEN s.billing_cycle = 'monthly' THEN p.price_monthly
    WHEN s.billing_cycle = 'yearly' THEN p.price_yearly / 12
    ELSE 0
  END) as mrr
FROM subscriptions s
JOIN plans p ON s.plan_id = p.id
WHERE s.status = 'active'
  AND s.current_period_end > NOW();
```

---

### 10. Feature Adoption Rate

**Definition**: Percentage of eligible users who have used a specific feature.

**Formula**: `(COUNT(DISTINCT user_id WHERE feature_event) / COUNT(DISTINCT user_id WHERE eligible)) * 100`

**Required Tables**: `events`, `users`, `features`

**Eligibility**: Users who have access to the feature (plan, role, etc.)

**Time Window**: Typically 30 days rolling

**SQL Implementation**:
```sql
WITH eligible AS (
  SELECT DISTINCT user_id
  FROM users u
  JOIN subscriptions s ON u.id = s.user_id
  JOIN plans p ON s.plan_id = p.id
  WHERE s.status = 'active'
    AND p.features->>'feature_x' = 'true'
),
adopters AS (
  SELECT DISTINCT user_id
  FROM events
  WHERE event_name = 'feature_x_used'
    AND timestamp >= NOW() - INTERVAL '30 days'
)
SELECT COUNT(DISTINCT a.user_id)::float / COUNT(DISTINCT e.user_id) * 100 as adoption_rate
FROM eligible e
LEFT JOIN adopters a ON e.user_id = a.user_id;
```

---

## Metric Calculation Standards

### Time Windows
- All timestamps in UTC
- Period boundaries: midnight UTC
- Rolling windows: relative to query time
- Fixed windows: calendar boundaries

### Data Quality
- Exclude test users (email contains 'test', 'dev', 'staging')
- Exclude internal IPs
- Handle null timestamps gracefully
- Deduplicate events (same user, same event, same second)

### Metric Versioning
- Each metric has a version number
- Changes require approval
- Backward compatibility maintained for 12 months

### Metric Registry
All metrics registered in `analytics/metrics/registry.py` with:
- Name, description, formula
- Owner team
- SLA (freshness, accuracy)
- Dependencies