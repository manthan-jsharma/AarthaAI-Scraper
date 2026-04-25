import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

scheduler = BackgroundScheduler()


def _run_async(coro):
    asyncio.run(coro)


def daily_pipeline():
    logger.info("Scheduled daily pipeline starting...")
    from agents.discovery_agent import run_discovery
    from agents.scraping_agent import scrape_all_brokers
    from insights.groq_engine import generate_insights_for_all
    from output.sheets import export_brokers_to_sheets

    async def pipeline():
        await run_discovery()
        await scrape_all_brokers()
        generate_insights_for_all()
        export_brokers_to_sheets()

    _run_async(pipeline())
    logger.info("Daily pipeline complete.")


def start_scheduler():
    # Run every day at 2 AM
    scheduler.add_job(
        daily_pipeline,
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_pipeline",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started — daily pipeline at 2:00 AM")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
