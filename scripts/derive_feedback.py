#!/usr/bin/env python3
"""
Derive product feedback, support tickets, and NPS from e-commerce event data.
Creates realistic feedback data based on user behavior patterns.
"""
import logging
import os
import random
import sys
import uuid
from datetime import timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from db.connection import get_sync_session
from db.schema.models import (
    Event,
    FeedbackSentiment,
    FeedbackSource,
    ProductFeedback,
    SupportTicket,
    TicketPriority,
    TicketStatus,
    User,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Feedback templates for different scenarios
FEEDBACK_TEMPLATES = {
    "positive": {
        FeedbackSource.NPS: [
            "Love the product! Great selection and fast shipping.",
            "Excellent experience, will definitely recommend.",
            "Best online store I've used. Easy to find what I need.",
            "Amazing customer service and quality products.",
        ],
        FeedbackSource.REVIEW: [
            "Perfect product, exactly as described. Fast delivery!",
            "Great quality for the price. Very satisfied.",
            "Excellent service, will buy again.",
            "Product exceeded expectations. Highly recommend.",
        ],
        FeedbackSource.FEATURE_REQUEST: [
            "Would love a wishlist feature to save items for later.",
            "A loyalty program would be great for frequent buyers.",
            "Mobile app would make shopping even easier.",
            "Option for scheduled deliveries would be helpful.",
        ],
    },
    "negative": {
        FeedbackSource.NPS: [
            "Shipping took too long and tracking was unreliable.",
            "Product quality didn't match description. Disappointed.",
            "Customer service was unhelpful when I had an issue.",
            "Website is confusing to navigate. Hard to find products.",
        ],
        FeedbackSource.REVIEW: [
            "Item arrived damaged. Return process was frustrating.",
            "Not as described. Quality is much lower than expected.",
            "Shipping was extremely slow with no updates.",
            "Wrong item sent. Still waiting for replacement.",
        ],
        FeedbackSource.FEATURE_REQUEST: [
            "Need better search filters - hard to find specific items.",
            "Wish there was a way to track price drops.",
            "Checkout process is too complicated.",
            "Mobile site is buggy and crashes often.",
        ],
    },
    "neutral": {
        FeedbackSource.NPS: [
            "It's okay. Nothing special but gets the job done.",
            "Average experience. Could be better, could be worse.",
            "Decent selection but prices are average.",
        ],
        FeedbackSource.REVIEW: [
            "Product is fine. Shipping was standard.",
            "Got what I ordered. Nothing remarkable.",
            "Average quality for the price point.",
        ],
        FeedbackSource.FEATURE_REQUEST: [
            "Dark mode would be nice to have.",
            "Email notifications for order updates would help.",
        ],
    },
}

SUPPORT_TICKET_TEMPLATES = {
    "shipping": {
        "subject": [
            "Where is my order?",
            "Shipping delay inquiry",
            "Package not delivered",
            "Tracking not updating",
        ],
        "body": [
            "My order {order_id} was supposed to arrive on {date} but hasn't shown up. Tracking hasn't updated in days.",
            "I placed an order a week ago and still no shipping confirmation. Can you check the status?",
            "The tracking shows delivered but I never received the package. Please investigate.",
        ],
        "category": "Shipping",
        "priority": TicketPriority.MEDIUM,
    },
    "product_issue": {
        "subject": [
            "Damaged item received",
            "Wrong product sent",
            "Product quality complaint",
            "Item not as described",
        ],
        "body": [
            "Received order {order_id} but the item is damaged. The packaging was intact but product is broken.",
            "I ordered {product_name} but received a completely different item. Need exchange or refund.",
            "The product quality is much lower than shown in photos. Very disappointed.",
        ],
        "category": "Product Issue",
        "priority": TicketPriority.HIGH,
    },
    "return_refund": {
        "subject": [
            "Return request",
            "Refund status inquiry",
            "Exchange request",
            "Return label not working",
        ],
        "body": [
            "I'd like to return order {order_id}. The item doesn't fit/work as expected.",
            "Requesting refund for order {order_id}. It's been 2 weeks since I returned it.",
            "Need to exchange for a different size. How do I get a return label?",
        ],
        "category": "Returns",
        "priority": TicketPriority.MEDIUM,
    },
    "account_billing": {
        "subject": [
            "Billing question",
            "Account access issue",
            "Payment failed",
            "Subscription cancellation",
        ],
        "body": [
            "I was charged twice for order {order_id}. Please refund the duplicate charge.",
            "Can't log into my account. Password reset email not arriving.",
            "My payment was declined but the order went through. Please check.",
        ],
        "category": "Billing",
        "priority": TicketPriority.HIGH,
    },
}

CATEGORIES = [
    "electronics", "clothing", "home", "sports", "books", "beauty",
    "automotive", "toys", "garden", "health"
]

PRODUCT_AREAS = [
    "checkout", "search", "product_pages", "account", "mobile_app",
    "shipping", "returns", "payments", "notifications", "recommendations"
]


class FeedbackDeriver:
    """Derive feedback and support tickets from user behavior."""

    def __init__(self):
        self.batch_size = 500
        self.stats = {
            "support_tickets": 0,
            "product_feedback": 0,
            "nps_responses": 0,
        }

    def analyze_users_for_feedback(self, session: Session) -> dict[str, dict]:
        """Analyze users to determine feedback likelihood and sentiment."""
        logger.info("Analyzing users for feedback generation...")

        # Get users with their event history
        users = session.query(User).filter(User.status != "churned").all()

        user_analysis = {}
        for user in users:
            # Get user events
            events = session.query(Event).filter(
                Event.user_id == user.id
            ).order_by(Event.timestamp).all()

            if not events:
                continue

            purchase_events = [e for e in events if e.event_name == "purchase"]
            total_events = len(events)
            total_purchases = len(purchase_events)

            # Calculate engagement metrics
            first_event = events[0].timestamp
            last_event = events[-1].timestamp
            days_active = (last_event - first_event).days + 1

            # Determine sentiment based on behavior
            # High engagement + purchases = positive
            # Low engagement or failed events = negative
            # Medium = neutral

            failed_events = [e for e in events if e.event_name in ["remove_from_cart"]]
            cart_abandonment = len([e for e in events if e.event_name == "add_to_cart"]) - total_purchases

            # Sentiment scoring
            sentiment_score = 0
            sentiment_score += total_purchases * 2
            sentiment_score += min(days_active, 30) * 0.5
            sentiment_score -= len(failed_events) * 1
            sentiment_score -= cart_abandonment * 0.5

            if sentiment_score > 10:
                sentiment = "positive"
            elif sentiment_score < 0:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            # Feedback probability based on engagement
            feedback_prob = min(0.3 + (total_purchases * 0.05) + (days_active * 0.01), 0.8)

            user_analysis[str(user.id)] = {
                "user": user,
                "total_events": total_events,
                "total_purchases": total_purchases,
                "days_active": days_active,
                "sentiment": sentiment,
                "feedback_prob": feedback_prob,
                "last_purchase": purchase_events[-1].timestamp if purchase_events else None,
                "categories": list(set(
                    e.event_properties.get("category_code", "general").split(".")[0]
                    for e in events if e.event_properties.get("category_code")
                ))[:3],
            }

        logger.info(f"Analyzed {len(user_analysis)} users")
        return user_analysis

    def generate_support_tickets(self, session: Session, user_analysis: dict) -> None:
        """Generate support tickets based on user behavior."""
        logger.info("Generating support tickets...")

        for user_id_str, data in user_analysis.items():
            user = data["user"]

            # Determine number of tickets (0-3 based on sentiment and activity)
            if data["sentiment"] == "negative":
                num_tickets = random.randint(1, 3)
            elif data["sentiment"] == "neutral":
                num_tickets = random.randint(0, 1)
            else:
                num_tickets = random.randint(0, 1) if random.random() < 0.2 else 0

            for _ in range(num_tickets):
                # Pick ticket type based on sentiment
                if data["sentiment"] == "negative":
                    ticket_type = random.choices(
                        ["shipping", "product_issue", "return_refund", "account_billing"],
                        weights=[0.4, 0.3, 0.2, 0.1]
                    )[0]
                else:
                    ticket_type = random.choice(["shipping", "account_billing"])

                template = SUPPORT_TICKET_TEMPLATES[ticket_type]

                # Random creation date within user's active period
                days_offset = random.randint(0, max(1, data["days_active"]))
                created_at = user.created_at + timedelta(days=days_offset)

                # 80% resolved
                status = TicketStatus.RESOLVED if random.random() < 0.8 else random.choice(
                    [TicketStatus.OPEN, TicketStatus.IN_PROGRESS]
                )

                ticket = SupportTicket(
                    user_id=user.id,
                    subject=random.choice(template["subject"]),
                    body=random.choice(template["body"]).format(
                        order_id=f"ORD-{uuid.uuid4().hex[:8].upper()}",
                        date=(created_at + timedelta(days=3)).strftime("%Y-%m-%d"),
                        product_name=f"Product {random.randint(1000, 9999)}",
                    ),
                    category=template["category"],
                    priority=template["priority"],
                    status=status,
                    created_at=created_at,
                    resolved_at=created_at + timedelta(days=random.randint(1, 5)) if status == TicketStatus.RESOLVED else None,
                    tags=[ticket_type, data["sentiment"]],
                    metadata_={"derived_from": "ecommerce_behavior"},
                )
                session.add(ticket)
                self.stats["support_tickets"] += 1

    def generate_product_feedback(self, session: Session, user_analysis: dict) -> None:
        """Generate product feedback (NPS, reviews, feature requests)."""
        logger.info("Generating product feedback...")

        for user_id_str, data in user_analysis.items():
            user = data["user"]

            # Generate feedback based on probability
            if random.random() > data["feedback_prob"]:
                continue

            # Number of feedback items (1-3)
            num_feedback = random.randint(1, 3)

            for _ in range(num_feedback):
                # Determine source
                source = random.choices(
                    [FeedbackSource.NPS, FeedbackSource.REVIEW, FeedbackSource.FEATURE_REQUEST, FeedbackSource.SURVEY],
                    weights=[0.3, 0.4, 0.2, 0.1]
                )[0]

                sentiment = data["sentiment"]
                templates = FEEDBACK_TEMPLATES[sentiment].get(source, FEEDBACK_TEMPLATES["neutral"].get(source, ["Feedback"]))

                # NPS score based on sentiment
                if source == FeedbackSource.NPS:
                    if sentiment == "positive":
                        rating = random.randint(8, 10)
                    elif sentiment == "negative":
                        rating = random.randint(0, 5)
                    else:
                        rating = random.randint(6, 7)
                elif source == FeedbackSource.REVIEW:
                    if sentiment == "positive":
                        rating = random.randint(4, 5)
                    elif sentiment == "negative":
                        rating = random.randint(1, 2)
                    else:
                        rating = 3
                else:
                    rating = None

                # Random creation date
                days_offset = random.randint(0, max(1, data["days_active"]))
                created_at = user.created_at + timedelta(days=days_offset)

                # Product area
                product_area = random.choice(PRODUCT_AREAS)
                if data["categories"]:
                    product_area = data["categories"][0]

                feedback = ProductFeedback(
                    user_id=user.id,
                    source=source,
                    rating=rating,
                    text=random.choice(templates),
                    product_area=product_area,
                    sentiment=FeedbackSentiment(sentiment),
                    created_at=created_at,
                    metadata_={
                        "derived_from": "ecommerce_behavior",
                        "user_sentiment": sentiment,
                        "user_purchases": data["total_purchases"],
                    },
                )
                session.add(feedback)

                if source == FeedbackSource.NPS:
                    self.stats["nps_responses"] += 1
                else:
                    self.stats["product_feedback"] += 1

    def run(self) -> None:
        """Main derivation process."""
        logger.info("Starting feedback and support ticket derivation")

        with get_sync_session() as session:
            # Analyze users
            user_analysis = self.analyze_users_for_feedback(session)

            # Generate support tickets
            self.generate_support_tickets(session, user_analysis)
            session.flush()

            # Generate product feedback
            self.generate_product_feedback(session, user_analysis)

            session.commit()
            logger.info(f"Final stats: {self.stats}")


def main():
    """Main entry point."""
    deriver = FeedbackDeriver()
    deriver.run()


if __name__ == "__main__":
    main()
