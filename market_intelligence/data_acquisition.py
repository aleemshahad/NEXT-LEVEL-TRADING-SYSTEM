import requests
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
import re

try:
    from .models import RawSourceData
except (ImportError, ValueError):
    from market_intelligence.models import RawSourceData

class DataSource(ABC):
    @abstractmethod
    def fetch_data(self) -> List[RawSourceData]:
        pass

class MarketNewsCrawler(DataSource):
    """Real Market News Scraper from Public RSS Feeds"""
    def __init__(self):
        self.feeds = [
            "https://search.cnbc.com/rs/search/view.xml?partnerId=2000&keywords=gold%20market",
            "https://www.marketwatch.com/posts/bull-market-news.rss",
            "https://search.cnbc.com/rs/search/view.xml?partnerId=2000&keywords=fed%20interest%20rates"
        ]

    def fetch_data(self) -> List[RawSourceData]:
        print("[INFO] Fetching LIVE Market News from Global Sources...")
        results = []
        for feed_url in self.feeds:
            try:
                response = requests.get(feed_url, timeout=10)
                if response.status_code != 200: continue
                
                root = ET.fromstring(response.content)
                platform = "CNBC/Reuters Feed"
                
                for item in root.findall('.//item'):
                    title = item.find('title').text if item.find('title') is not None else ""
                    description = item.find('description').text if item.find('description') is not None else ""
                    link = item.find('link').text if item.find('link') is not None else ""
                    
                    full_content = f"{title}: {description}"
                    # Clean HTML tags
                    full_content = re.sub('<[^<]+?>', '', full_content)
                    
                    results.append(RawSourceData(
                        content=full_content[:500], # Keep it concise
                        source_url=link,
                        platform=platform,
                        timestamp=datetime.now(),
                        author_id="Market Crawler",
                        metadata={"feed": feed_url}
                    ))
                    if len(results) >= 10: break # Don't overload
            except Exception as e:
                print(f"   [WARN] Error fetching feed: {e}")
        return results

class InstitutionalInsightCrawler(DataSource):
    """Scrapes Central Bank Sentiment & Macro Sentiment"""
    def fetch_data(self) -> List[RawSourceData]:
        print("[INFO] Fetching Institutional Macro Insights...")
        # Placeholder for more complex scraping (e.g. FOMC Statements)
        results = []
        try:
            url = "https://www.marketwatch.com/rss/topstories"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for i, item in enumerate(root.findall('.//item')):
                    if i >= 5: break
                    results.append(RawSourceData(
                        content=f"Macro Alert: {item.find('title').text}",
                        source_url=item.find('link').text,
                        platform="Institutional Feed",
                        timestamp=datetime.now(),
                        author_id="Quant Bot",
                        metadata={"type": "Institutional"}
                    ))
        except: pass
        return results

class DataAcquisitionService:
    def __init__(self):
        self.sources: List[DataSource] = [
            MarketNewsCrawler(),
            InstitutionalInsightCrawler()
        ]

    def aggregate_data(self) -> List[RawSourceData]:
        all_data = []
        for source in self.sources:
            try:
                data = source.fetch_data()
                all_data.extend(data)
            except Exception as e:
                print(f"   [ERROR] fetching from source {source}: {e}")
        
        if not all_data:
            print("! Warning: No live data collected. Market intelligence might be stale.")
            
        print(f"[SUCCESS] Aggregated {len(all_data)} REAL-TIME intelligence points.")
        return all_data
