import asyncio
from pathlib import Path

# Add project root to path if needed, though running via `PYTHONPATH=.` handles this
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.universe.universe import PriorityList, load_universe
from src.models.company import Company, CompanyType, PriorityTier
from src.pipeline.runner import PipelineOrchestrator

async def run_downloads():
    universe = load_universe()
    priority = PriorityList()
    priority_companies = priority.get_priority_companies(universe)
    
    print(f"Found {len(priority_companies)} high-priority companies.")

    for pc in priority_companies:
        print(f"\n--- Starting Download for: {pc.name} (Issuer ID: {pc.issuer_no}) ---")
        # Sanitize slug
        slug = pc.name.lower().replace(" ", "_").replace(".", "").replace('"', "").replace("'", "")
        
        comp = Company(
            slug=slug,
            name=pc.name,
            company_type=CompanyType.TASE_TRADED,
            priority=PriorityTier.HIGH,
            tase_company_id=pc.issuer_no,
            tase_id=pc.corporate_no
        )
        
        orch = PipelineOrchestrator(
            company=comp,
            override_provider=None
        )
        
        try:
            # We want to run 5 years back, only "download" step
            await orch.run(
                years_back=5,
                skip_analyze=True,
                skip_upload=True,
                requested_steps=["download"]
            )
        except Exception as e:
            print(f"Error downloading {pc.name}: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_downloads())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
