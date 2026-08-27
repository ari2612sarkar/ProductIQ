#!/usr/bin/env python3
"""
Derive subscriptions, payments, and other SaaS entities from e-commerce event data.
This creates realistic subscription data based on purchase patterns.
"""
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from db.connection import get_sync_session
from db.schema.models import (
    Event,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionStatus,
    User,
    UserStatus,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SubscriptionDeriver:
    """Derive subscription data from e-commerce events."""

    def __init__(self):
        self.batch_size = 1000
        self.stats = {
            "subscriptions": 0,
            "payments": 0,
            "premium_users": 0,
        }

    def analyze_user_behavior(self, session: Session) -> dict[str, dict]:
        """Analyze user purchase behavior to determine subscription eligibility."""
        logger.info("Analyzing user purchase behavior...")

        # Get users with purchase events
        purchase_events = session.query(Event).filter(
            Event.event_name == "purchase"
        ).all()

        user_purchases: dict[uuid.UUID, list[Event]] = {}
        for event in purchase_events:
            if event.user_id not in user_purchases:
                user_purchases[event.user_id] = []
            user_purchases[event.user_id].append(event)

        # Analyze each user
        user_analysis = {}
        for user_id, events in user_purchases.items():
            events.sort(key=lambda e: e.timestamp)

            first_purchase = events[0].timestamp
            last_purchase = events[-1].timestamp
            total_purchases = len(events)

            # Calculate total revenue
            total_revenue = sum(
                Decimal(str(e.event_properties.get("price", 0)))
                for e in events
            )

            # Determine if user is a "subscriber" (repeat purchaser)
            is_subscriber = total_purchases >= 2

            # Calculate average days between purchases
            if len(events) > 1:
                days_between = [
                    (events[i].timestamp - events[i-1].timestamp).days
                    for i in range(1, len(events))
                ]
                avg_days_between = sum(days_between) / len(days_between)
            else:
                avg_days_between = 30

            user_analysis[user_id] = {
                "first_purchase": first_purchase,
                "last_purchase": last_purchase,
                "total_purchases": total_purchases,
                "total_revenue": total_revenue,
                "is_subscriber": is_subscriber,
                "avg_days_between": avg_days_between,
                "events": events,
            }

        logger.info(f"Analyzed {len(user_analysis)} users with purchases")
        logger.info(f"Potential subscribers: {sum(1 for u in user_analysis.values() if u['is_subscriber'])}")

        return user_analysis

    def create_plans(self, session: Session) -> dict[str, uuid.UUID]:
        """Create subscription plans."""
        plans_data = [
            {
                "name": "Free",
                "price_monthly": Decimal("0.00"),
                "price_yearly": Decimal("0.00"),
                "features": {"tier": "free", "support": "community"},
            },
            {
                "name": "Basic",
                "price_monthly": Decimal("9.99"),
                "price_yearly": Decimal("99.99"),
                "features": {"tier": "basic", "support": "email", "features": ["core"]},
            },
            {
                "name": "Pro",
                "price_monthly": Decimal("29.99"),
                "price_yearly": Decimal("299.99"),
                "features": {"tier": "pro", "support": "priority", "features": ["core", "advanced", "api"]},
            },
            {
                "name": "Enterprise",
                "price_monthly": Decimal("99.99"),
                "price_yearly": Decimal("999.99"),
                "features": {"tier": "enterprise", "support": "dedicated", "features": ["core", "advanced", "api", "custom"]},
            },
        ]

        plan_map = {}
        for plan_data in plans_data:
            plan = session.query(Plan).filter(Plan.name == plan_data["name"]).first()
            if not plan:
                plan = Plan(
                    name=plan_data["name"],
                    price_monthly=plan_data["price_monthly"],
                    price_yearly=plan_data["price_yearly"],
                    features=plan_data["features"],
                    is_active=True,
                )
                session.add(plan)
                session.flush()
            plan_map[plan_data["name"]] = plan.id

        return plan_map

    def assign_user_tier(self, user_data: dict) -> str:
        """Assign subscription tier based on user behavior."""
        total_revenue = float(user_data["total_revenue"])
        total_purchases = user_data["total_purchases"]

        if total_purchases >= 10 or total_revenue >= 500:
            return "Enterprise"
        if total_purchases >= 5 or total_revenue >= 200:
            return "Pro"
        if total_purchases >= 2 or total_revenue >= 50:
            return "Basic"
        return "Free"

    def create_subscriptions(self, session: Session, user_analysis: dict, plan_map: dict[str, uuid.UUID]) -> None:
        """Create subscriptions for users."""
        logger.info("Creating subscriptions...")

        for user_id, data in user_analysis.items():
            tier = self.assign_user_tier(data)
            plan_id = plan_map[tier]

            # Determine subscription status based on recency
            now = datetime.now(timezone.utc)
            days_since_last = (now - data["last_purchase"]).days

            if tier == "Free":
                status = SubscriptionStatus.ACTIVE
            elif days_since_last > 90:
                status = SubscriptionStatus.CANCELLED
            elif days_since_last > 60:
                status = SubscriptionStatus.PAST_DUE
            else:
                status = SubscriptionStatus.ACTIVE

            # Subscription period
            started_at = data["first_purchase"]
            if status == SubscriptionStatus.CANCELLED:
                current_period_end = data["last_purchase"] + timedelta(days=30)
                cancelled_at = data["last_purchase"] + timedelta(days=15)
            else:
                current_period_end = now + timedelta(days=30)
                cancelled_at = None

            # Billing cycle - yearly for high value, monthly for others
            billing_cycle = "yearly" if tier in ["Pro", "Enterprise"] and data["total_purchases"] > 3 else "monthly"

            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                status=status,
                started_at=started_at,
                cancelled_at=cancelled_at,
                current_period_start=started_at,
                current_period_end=current_period_end,
                billing_cycle=billing_cycle,
                trial_ends_at=started_at + timedelta(days=14) if tier != "Free" else None,
                metadata_={
                    "derived_from": "ecommerce_purchases",
                    "total_purchases": data["total_purchases"],
                    "total_revenue": str(data["total_revenue"]),
                },
            )
            session.add(subscription)
            session.flush()

            self.stats["subscriptions"] += 1

            if tier != "Free":
                self.stats["premium_users"] += 1

            # Create payments for this subscription
            self._create_payments(session, subscription, data, tier)

    def _create_payments(self, session: Session, subscription: Subscription, user_data: dict, tier: str) -> None:
        """Create payment records for a subscription."""
        plan = session.query(Plan).filter(Plan.id == subscription.plan_id).first()
        if not plan:
            return

        amount = plan.price_yearly if subscription.billing_cycle == "yearly" else plan.price_monthly

        # Create initial payment
        payment = Payment(
            subscription_id=subscription.id,
            amount=amount,
            currency="USD",
            status=PaymentStatus.SUCCEEDED,
            paid_at=subscription.started_at,
            invoice_number=f"INV-{subscription.id.hex[:8].upper()}",
            payment_method="credit_card",
            metadata_={"derived_from": "ecommerce_purchases"},
        )
        session.add(payment)
        self.stats["payments"] += 1

        # Create recurring payments for active subscriptions
        if subscription.status == SubscriptionStatus.ACTIVE:
            periods = 12 if subscription.billing_cycle == "yearly" else 6
            now = datetime.now(timezone.utc)
            for i in range(1, periods):
                paid_at = subscription.started_at + timedelta(
                    days=365 if subscription.billing_cycle == "yearly" else 30 * i
                )

                # Stop if past current period
                if paid_at > now:
                    break

                # 5% chance of failed payment
                import random
                status = PaymentStatus.FAILED if random.random() < 0.05 else PaymentStatus.SUCCEEDED

                payment = Payment(
                    subscription_id=subscription.id,
                    amount=amount,
                    currency="USD",
                    status=status,
                    paid_at=paid_at if status == PaymentStatus.SUCCEEDED else None,
                    invoice_number=f"INV-{subscription.id.hex[:8].upper()}-{i+1}",
                    payment_method="credit_card",
                    failure_reason="Insufficient funds" if status == PaymentStatus.FAILED else None,
                    metadata_={"derived_from": "ecommerce_purchases", "period": i+1},
                )
                session.add(payment)
                self.stats["payments"] += 1

    def update_user_plans(self, session: Session, user_analysis: dict, plan_map: dict[str, uuid.UUID]) -> None:
        """Update user plan_id based on derived subscription."""
        logger.info("Updating user plans...")

        for user_id, data in user_analysis.items():
            tier = self.assign_user_tier(data)
            plan_id = plan_map[tier]

            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user.plan_id = plan_id
                if tier != "Free":
                    user.status = UserStatus.ACTIVE
                    user.metadata_["subscription_tier"] = tier
                    user.metadata_["derived_subscription"] = True

    def run(self) -> None:
        """Main derivation process."""
        logger.info("Starting subscription derivation from e-commerce data")

        with get_sync_session() as session:
            # Create plans
            plan_map = self.create_plans(session)
            session.flush()

            # Analyze user behavior
            user_analysis = self.analyze_user_behavior(session)

            # Update user plans
            self.update_user_plans(session, user_analysis, plan_map)

            # Create subscriptions
            self.create_subscriptions(session, user_analysis, plan_map)

            session.commit()
            logger.info(f"Final stats: {self.stats}")


def main():
    """Main entry point."""
    deriver = SubscriptionDeriver()
    deriver.run()


if __name__ == "__main__":
    main()
