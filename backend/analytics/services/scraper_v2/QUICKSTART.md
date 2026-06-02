# Quick Start Guide - eBay Scraper V2

## Installation

No additional dependencies needed! The refactored scraper uses the same packages as the old one.

## Basic Usage

### Simple One-Liner

```python
from analytics.services.scraper_v2 import scrape_ebay

# Scrape and analyze in one line
report = await scrape_ebay("2010 Toyota Prius battery", max_pages=10)

print(f"Found {report['counts']['kept']['total']} relevant listings")
print(f"Cost: ${report['metrics']['estimated_cost']:.4f}")
```

### With More Control

```python
from analytics.services.scraper_v2 import EbayScraper

async with EbayScraper(
    query="Tesla Model 3 parts",
    max_pages=20,
    items_per_page=240,
    vehicle_year=2020,
    vehicle_make="Tesla",
    vehicle_model="Model 3",
) as scraper:
    report = await scraper.scrape()

    # Access metrics
    print(f"Duration: {scraper.metrics.duration_seconds:.2f}s")
    print(f"API calls: {scraper.metrics.total_api_calls}")
    print(f"Categories: {len(report['category_analysis'])}")
```

### In Celery Tasks

```python
from analytics.services.scraper_v2 import scrape_ebay
from celery import shared_task

@shared_task
def scrape_parts(query):
    # Run async code in Celery
    report = asyncio.run(scrape_ebay(query, max_pages=10))
    return report
```

### Backward Compatible

The old interface still works:

```python
from analytics.services.scraper_v2.compat import ScrapingBeeAIScraper

scraper = ScrapingBeeAIScraper("Toyota parts", max_pages=10)
report = await scraper.scrape()
```

## Configuration

### Environment Variables

Create a `.env` file or set in Django settings:

```bash
SCRAPING_BEE_API_KEY=your_scrapingbee_key
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BATCH_SIZE=60
DEEPSEEK_MAX_CONCURRENT=10
SCRAPINGBEE_MAX_CONCURRENT=20
```

### Programmatic Configuration

```python
from analytics.services.scraper_v2.config import Settings

settings = Settings(
    SCRAPING_BEE_API_KEY="your_key",
    DEEPSEEK_API_KEY="your_key",
    DEEPSEEK_MAX_CONCURRENT=15,  # Custom concurrency
)

async with EbayScraper(query="parts", settings=settings) as scraper:
    report = await scraper.scrape()
```

## Understanding the Report

### Report Structure

```python
{
    "query": "2010 Toyota Prius battery",
    "category_id": 6030,
    "scraped_at": "2024-12-02T10:30:00Z",

    "counts": {
        "raw": {"active": 500, "sold": 300, "total": 800},
        "kept": {"active": 400, "sold": 250, "total": 650},
        "dropped": 150
    },

    "category_analysis": [
        {
            "category": "HV Battery Pack",
            "opportunity_score": 85,
            "optimal_price": 450.00,
            "active_count": 20,
            "sold_count": 35,
            "sell_through_rate": 63.6,
            "recommendation": "Excellent opportunity..."
        }
    ],

    "metrics": {
        "total_api_calls": 45,
        "deepseek_calls": 5,
        "estimated_cost": 0.00175,
        "duration_seconds": 42.3
    }
}
```

### Key Metrics

```python
# Access specific metrics
metrics = report['metrics']
print(f"Total cost: ${metrics['estimated_cost']:.4f}")
print(f"Time taken: {metrics['duration_seconds']:.1f}s")
print(f"API calls: {metrics['total_api_calls']}")

# Top categories
for cat in report['category_analysis'][:5]:
    print(f"{cat['category']}: ${cat['optimal_price']} (score: {cat['opportunity_score']})")
```

## Performance Tips

### 1. Adjust Concurrency

```python
from analytics.services.scraper_v2.config import Settings

# More aggressive (faster but more likely to hit rate limits)
settings = Settings(
    DEEPSEEK_MAX_CONCURRENT=20,
    SCRAPINGBEE_MAX_CONCURRENT=30,
)

# More conservative (slower but safer)
settings = Settings(
    DEEPSEEK_MAX_CONCURRENT=5,
    SCRAPINGBEE_MAX_CONCURRENT=10,
)
```

### 2. Limit Pages for Testing

```python
# Quick test - 2 pages only
report = await scrape_ebay(query, max_pages=2)

# Full production - 50 pages
report = await scrape_ebay(query, max_pages=50)
```

### 3. Monitor Costs

```python
report = await scrape_ebay(query, max_pages=10)

# Check if cost is acceptable
if report['metrics']['estimated_cost'] > 5.0:
    print("Warning: High API cost!")
```

## Error Handling

```python
from analytics.services.scraper_v2 import EbayScraper

try:
    async with EbayScraper(query="parts") as scraper:
        report = await scraper.scrape()

except Exception as exc:
    print(f"Scraping failed: {exc}")

    # Errors are tracked in metrics
    if hasattr(scraper, 'metrics'):
        for error in scraper.metrics.errors:
            print(f"Error: {error}")
```

## Common Patterns

### Pattern 1: Multi-Vehicle Analysis

```python
vehicles = [
    ("2010", "Toyota", "Prius"),
    ("2012", "Honda", "Civic"),
    ("2015", "Ford", "Focus"),
]

reports = []
for year, make, model in vehicles:
    query = f"{year} {make} {model} parts"
    report = await scrape_ebay(
        query,
        vehicle_year=int(year),
        vehicle_make=make,
        vehicle_model=model,
        max_pages=5,
    )
    reports.append(report)

# Compare opportunities across vehicles
for report in reports:
    vehicle = f"{report['vehicle_info']['year']} {report['vehicle_info']['make']}"
    total_net = report['part_out_summary']['estimated_total_net']
    print(f"{vehicle}: ${total_net:.2f}")
```

### Pattern 2: Cost-Aware Scraping

```python
MAX_COST = 1.00  # Maximum $1 per scrape

report = await scrape_ebay(query, max_pages=20)

if report['metrics']['estimated_cost'] > MAX_COST:
    # Reduce scope for next time
    print(f"Cost ${report['metrics']['estimated_cost']:.2f} exceeded ${MAX_COST}")
    print("Consider reducing max_pages")
```

### Pattern 3: Progress Tracking

```python
from analytics.services.scraper_v2 import EbayScraper

async with EbayScraper(query="parts", max_pages=50) as scraper:
    # Start scrape
    print("Scraping started...")

    report = await scraper.scrape()

    # Show progress
    print(f"Completed in {scraper.metrics.duration_seconds:.1f}s")
    print(f"API calls: {scraper.metrics.total_api_calls}")
    print(f"Found {len(report['category_analysis'])} categories")
```

## Troubleshooting

### Issue: Rate Limit Errors

**Solution:** Reduce concurrency

```python
settings = Settings(DEEPSEEK_MAX_CONCURRENT=5, SCRAPINGBEE_MAX_CONCURRENT=10)
```

### Issue: High Costs

**Solution:** Reduce pages or enable caching

```python
# Reduce pages
report = await scrape_ebay(query, max_pages=10)

# Or use caching (if enabled)
settings = Settings(ENABLE_CACHE=True, CACHE_TTL_SECONDS=3600)
```

### Issue: Slow Performance

**Solution:** Increase concurrency (if rate limits allow)

```python
settings = Settings(DEEPSEEK_MAX_CONCURRENT=15, SCRAPINGBEE_MAX_CONCURRENT=25)
```

### Issue: Memory Issues

**Solution:** Process in batches

```python
# Instead of scraping all 50 pages at once
for batch_start in range(0, 50, 10):
    report = await scrape_ebay(query, max_pages=10, start_page=batch_start)
    # Process batch...
```

## Testing

### Quick Test

```python
# Small scrape for testing
report = await scrape_ebay("test query", max_pages=2)

assert report['counts']['raw']['total'] > 0
assert 'metrics' in report
assert report['metrics']['estimated_cost'] < 0.50
```

### Integration Test

```python
import pytest

@pytest.mark.asyncio
async def test_scraper():
    from analytics.services.scraper_v2 import scrape_ebay

    report = await scrape_ebay("Toyota Prius parts", max_pages=1)

    assert 'counts' in report
    assert 'metrics' in report
    assert report['metrics']['total_api_calls'] > 0
```

## Next Steps

1. Read the [README.md](README.md) for architecture details
2. Check [REFACTORING_SUMMARY.md](../../../../REFACTORING_SUMMARY.md) for improvement details
3. Explore the code in `scraper_v2/` directory
4. Run your first scrape and check the metrics!

## Support

If you encounter issues:
1. Check the error messages in `metrics.errors`
2. Review configuration settings
3. Check API key validity
4. Verify rate limits aren't exceeded

## Examples Repository

See more examples in the `examples/` directory (coming soon):
- `basic_scrape.py` - Simple scraping
- `batch_processing.py` - Process multiple queries
- `cost_tracking.py` - Monitor and limit costs
- `celery_integration.py` - Celery task examples

---

Happy scraping! 🚀
