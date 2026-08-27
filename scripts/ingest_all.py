#!/usr/bin/env python3
"""
Master data ingestion script.
Orchestrates ingestion of all real datasets and derived data.
"""
import argparse
import logging
import os
import subprocess
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_script(script_name: str, args: list = None) -> bool:
    """Run a Python script as subprocess."""
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    cmd = [sys.executable, script_path] + (args or [])

    logger.info(f"Running: {' '.join(cmd)}")
    start = time.time()

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=3600)
        logger.info(f"Completed in {time.time() - start:.1f}s")
        if result.stdout:
            logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Script failed: {e}")
        if e.stdout:
            logger.error(f"STDOUT: {e.stdout}")
        if e.stderr:
            logger.error(f"STDERR: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("Script timed out after 1 hour")
        return False


def init_database() -> bool:
    """Initialize database schema."""
    logger.info("=" * 60)
    logger.info("STEP 1: Initializing database schema")
    logger.info("=" * 60)

    return run_script("init_db.py")


def ingest_ecommerce_events(sample_size: int) -> bool:
    """Ingest e-commerce events from HuggingFace."""
    logger.info("=" * 60)
    logger.info("STEP 2: Ingesting e-commerce events from HuggingFace")
    logger.info("=" * 60)

    return run_script("ingest_ecommerce_data.py", ["--sample", str(sample_size)])


def ingest_upworthy_experiments(sample_size: int = None) -> bool:
    """Ingest Upworthy A/B test experiments."""
    logger.info("=" * 60)
    logger.info("STEP 3: Ingesting Upworthy A/B test experiments")
    logger.info("=" * 60)

    args = []
    if sample_size:
        args.extend(["--sample", str(sample_size)])

    return run_script("ingest_upworthy_data.py", args)


def derive_subscriptions() -> bool:
    """Derive subscriptions from purchase behavior."""
    logger.info("=" * 60)
    logger.info("STEP 4: Deriving subscriptions from purchase data")
    logger.info("=" * 60)

    return run_script("derive_subscriptions.py")


def derive_feedback() -> bool:
    """Derive feedback and support tickets."""
    logger.info("=" * 60)
    logger.info("STEP 5: Deriving feedback and support tickets")
    logger.info("=" * 60)

    return run_script("derive_feedback.py")


def refresh_materialized_views() -> bool:
    """Refresh materialized views."""
    logger.info("=" * 60)
    logger.info("STEP 6: Refreshing materialized views")
    logger.info("=" * 60)

    return run_script("refresh_mviews.py")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Master data ingestion pipeline")
    parser.add_argument("--sample", type=int, default=100000, help="Sample size for e-commerce data")
    parser.add_argument("--upworthy-sample", type=int, default=None, help="Sample size for Upworthy data")
    parser.add_argument("--skip-steps", type=str, default="", help="Comma-separated steps to skip (1-6)")
    parser.add_argument("--only-steps", type=str, default="", help="Comma-separated steps to run (1-6)")
    args = parser.parse_args()

    skip_steps = set(args.skip_steps.split(",")) if args.skip_steps else set()
    only_steps = set(args.only_steps.split(",")) if args.only_steps else None

    steps = [
        ("1", "init_database", lambda: init_database()),
        ("2", "ingest_ecommerce_events", lambda: ingest_ecommerce_events(args.sample)),
        ("3", "ingest_upworthy_experiments", lambda: ingest_upworthy_experiments(args.upworthy_sample)),
        ("4", "derive_subscriptions", lambda: derive_subscriptions()),
        ("5", "derive_feedback", lambda: derive_feedback()),
        ("6", "refresh_materialized_views", lambda: refresh_materialized_views()),
    ]

    logger.info("Starting master data ingestion pipeline")
    logger.info(f"Sample size: {args.sample}")

    for step_num, step_name, step_func in steps:
        if only_steps and step_num not in only_steps:
            logger.info(f"Skipping step {step_num} ({step_name}) - not in only-steps")
            continue

        if step_num in skip_steps:
            logger.info(f"Skipping step {step_num} ({step_name})")
            continue

        success = step_func()
        if not success:
            logger.error(f"Step {step_num} ({step_name}) failed! Stopping pipeline.")
            sys.exit(1)

    logger.info("=" * 60)
    logger.info("All ingestion steps completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
