import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from database.client import (
    get_all_brokers, get_brokers_by_area, get_client,
    create_pipeline_run, complete_pipeline_run, fail_pipeline_run,
    get_pipeline_runs, get_rankings_for_run, get_broker_score_history,
)
from scheduler.jobs import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    logger.info("Scheduler started")
    yield
    stop_scheduler()
    logger.info("Scheduler stopped")


app = FastAPI(
    title="Real Estate Broker Ranker",
    description="AI-powered digital presence ranking for Bangalore real estate brokers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "running", "message": "Real Estate Broker Ranker API"}


@app.get("/brokers")
def list_brokers(
    area: str = Query(None, description="Filter by area e.g. Koramangala"),
    limit: int = Query(100, le=500),
):
    if area:
        return get_brokers_by_area(area)
    return get_all_brokers(limit=limit)


@app.get("/brokers/{broker_id}")
def get_broker(broker_id: str):
    result = get_client().table("brokers").select("*").eq("id", broker_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Broker not found")
    return result.data[0]


@app.get("/areas")
def list_areas():
    result = get_client().table("brokers").select("area").execute()
    areas = sorted({r["area"] for r in result.data if r.get("area")})
    return areas


@app.post("/run/discover")
async def run_discovery(background_tasks: BackgroundTasks):
    from agents.discovery_agent import run_discovery

    background_tasks.add_task(run_discovery)
    return {"status": "discovery started in background"}


@app.post("/run/scrape/{broker_id}")
async def run_scrape(broker_id: str, background_tasks: BackgroundTasks):
    from agents.scraping_agent import scrape_broker

    background_tasks.add_task(scrape_broker, broker_id)
    return {"status": f"scraping started for broker {broker_id}"}


@app.post("/run/full-pipeline")
async def run_full_pipeline(background_tasks: BackgroundTasks):
    from agents.discovery_agent import run_discovery
    from agents.scraping_agent import scrape_all_brokers

    async def pipeline():
        from insights.groq_engine import generate_insights_for_all

        run = create_pipeline_run()
        run_id = run.get("id")
        run_number = run.get("run_number")

        try:
            brokers = await run_discovery()
            await scrape_all_brokers(pipeline_run_id=run_id, run_number=run_number)
            await asyncio.to_thread(generate_insights_for_all)
            complete_pipeline_run(run_id, brokers_scraped=len(brokers))
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            if run_id:
                fail_pipeline_run(run_id)
            raise

    background_tasks.add_task(pipeline)
    return {"status": "full pipeline started in background"}


@app.post("/run/export-sheets")
async def export_to_sheets(background_tasks: BackgroundTasks):
    from output.sheets import export_brokers_to_sheets

    background_tasks.add_task(export_brokers_to_sheets)
    return {"status": "export to Google Sheets started"}


@app.post("/run/rescore")
async def rescore_all(background_tasks: BackgroundTasks):
    """Re-score all brokers and record a pipeline run snapshot — use this to backfill history."""
    from database.client import get_all_brokers
    from scoring.engine import calculate_and_save_scores

    def _rescore():
        run = create_pipeline_run()
        run_id = run.get("id")
        run_number = run.get("run_number")
        brokers = get_all_brokers(limit=500)
        success = 0
        for broker in brokers:
            try:
                calculate_and_save_scores(broker, pipeline_run_id=run_id, run_number=run_number)
                success += 1
            except Exception as e:
                logger.error(f"Rescore failed for {broker.get('name')}: {e}")
        complete_pipeline_run(run_id, brokers_scraped=success)
        logger.info(f"Rescore complete — run #{run_number}, {success} brokers")

    background_tasks.add_task(_rescore)
    return {"status": "rescore started in background"}


@app.get("/rankings/runs")
def list_pipeline_runs():
    return get_pipeline_runs()


@app.get("/rankings/run/{pipeline_run_id}")
def rankings_for_run(pipeline_run_id: str):
    return get_rankings_for_run(pipeline_run_id)


@app.get("/rankings/broker/{broker_id}/history")
def broker_score_history(broker_id: str):
    return get_broker_score_history(broker_id)


@app.get("/health")
def health():
    return {"status": "ok"}
