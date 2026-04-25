from agents.scrapegraph_config import SCRAPEGRAPH_CONFIG
from scrapegraphai.graphs import SmartScraperGraph

PROMPT = "Extract all real estate agent or broker names, areas, and phone numbers from this page. Return as a JSON list."

URLS = [
    ("99acres", "https://www.99acres.com/real-estate-agents-in-bangalore-ffid"),
    ("JustDial", "https://www.justdial.com/Bangalore/Real-Estate-Agents"),
    ("Housing", "https://housing.com/agents/bangalore"),
]

for name, url in URLS:
    print(f"\nTesting {name}: {url}")
    try:
        graph = SmartScraperGraph(prompt=PROMPT, source=url, config=SCRAPEGRAPH_CONFIG)
        result = graph.run()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")
