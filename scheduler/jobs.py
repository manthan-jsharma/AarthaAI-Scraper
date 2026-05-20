import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

scheduler = BackgroundScheduler()

# Prevents two pipeline runs overlapping if one takes longer than expected
_pipeline_running = False


def run_full_pipeline():
    global _pipeline_running

    if _pipeline_running:
        logger.warning("Pipeline already running — skipping this trigger")
        return

    _pipeline_running = True
    logger.info("Scheduled pipeline starting...")

    async def pipeline():
        from agents.discovery_agent import run_discovery
        from agents.scraping_agent import scrape_all_brokers
        from insights.groq_engine import generate_insights_for_all
        from database.client import create_pipeline_run, complete_pipeline_run, fail_pipeline_run

        run = create_pipeline_run()
        run_id = run.get("id")
        run_number = run.get("run_number")

        try:
            brokers = await run_discovery()
            await scrape_all_brokers(pipeline_run_id=run_id, run_number=run_number)
            await asyncio.to_thread(generate_insights_for_all)
            complete_pipeline_run(run_id, brokers_scraped=len(brokers))
            logger.info(f"Scheduled pipeline complete — run #{run_number}, {len(brokers)} brokers")
        except Exception as e:
            logger.error(f"Scheduled pipeline failed: {e}")
            if run_id:
                fail_pipeline_run(run_id)

    try:
        asyncio.run(pipeline())
    finally:
        _pipeline_running = False


def start_scheduler():
    # 3:00 PM IST
    scheduler.add_job(
        run_full_pipeline,
        trigger=CronTrigger(hour=15, minute=0, timezone="Asia/Kolkata"),
        id="pipeline_3pm",
        replace_existing=True,
    )
    # 7:00 PM IST
    scheduler.add_job(
        run_full_pipeline,
        trigger=CronTrigger(hour=19, minute=0, timezone="Asia/Kolkata"),
        id="pipeline_7pm",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — pipeline runs at 3:00 PM and 7:00 PM IST")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
