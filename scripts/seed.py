"""Seed database with initial data: sources, categories, and a test user."""

import os
import sys
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models import Base, Category, Source, User, UserPreference

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://newssnap:newssnap@localhost:5432/newssnap")

CATEGORIES = [
    ("National", "national", "India domestic news, governance, policy", "🇮🇳", 1),
    ("International", "international", "Global news, foreign affairs, geopolitics", "🌍", 2),
    ("Politics", "politics", "Elections, parties, parliament, state politics", "🏛️", 3),
    ("Business", "business", "Corporate, startups, economy, GDP, trade", "💼", 4),
    ("Finance", "finance", "Markets, stocks, mutual funds, crypto, RBI, banking", "📈", 5),
    ("Sports", "sports", "Cricket, football, Olympics, IPL, kabaddi", "🏏", 6),
    ("Technology", "technology", "AI, gadgets, apps, internet, social media", "💻", 7),
    ("Science", "science", "Space, research, discoveries, ISRO", "🔬", 8),
    ("Automobile", "automobile", "Cars, bikes, EVs, launches, reviews", "🚗", 9),
    ("Education", "education", "Exams, results, universities, NEP, scholarships", "🎓", 10),
    ("Health", "health", "Medical, fitness, diseases, pharma", "🏥", 11),
    ("Entertainment", "entertainment", "Bollywood, OTT, music, celebrities, TV", "🎬", 12),
    ("Lifestyle", "lifestyle", "Food, travel, fashion, relationships, wellness", "✨", 13),
    ("Crime", "crime", "Law, court verdicts, scams, cybercrime", "⚖️", 14),
    ("Environment", "environment", "Climate, pollution, wildlife, disasters, weather", "🌿", 15),
    ("Jobs", "jobs", "Government jobs, sarkari naukri, recruitment", "💼", 16),
    ("Defence", "defence", "Military, armed forces, defence deals, border security", "🛡️", 17),
    ("Real Estate", "real_estate", "Property, housing, RERA, smart cities", "🏠", 18),
    ("Opinion", "opinion", "Editorials, columns, analysis, debates", "💬", 19),
]

SOURCES = [
    ("The Hindu", "https://www.thehindu.com", "https://www.thehindu.com/feeder/default.rss", "rss", "en", "national"),
    ("Times of India", "https://timesofindia.indiatimes.com", "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "rss", "en", "national"),
    ("NDTV", "https://www.ndtv.com", "https://feeds.feedburner.com/ndtvnews-top-stories", "rss", "en", "national"),
    ("Indian Express", "https://indianexpress.com", "https://indianexpress.com/feed/", "rss", "en", "national"),
    ("Hindustan Times", "https://www.hindustantimes.com", "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", "rss", "en", "national"),
    ("Mint", "https://www.livemint.com", "https://www.livemint.com/rss/news", "rss", "en", "business"),
    ("Economic Times", "https://economictimes.indiatimes.com", "https://economictimes.indiatimes.com/rssfeedstopstories.cms", "rss", "en", "finance"),
    ("Moneycontrol", "https://www.moneycontrol.com", "https://www.moneycontrol.com/rss/latestnews.xml", "rss", "en", "finance"),
    ("ESPN Cricinfo", "https://www.espncricinfo.com", None, "static", "en", "sports"),
    ("Gadgets 360", "https://www.gadgets360.com", "https://www.gadgets360.com/rss/news", "rss", "en", "technology"),
    ("The Wire", "https://thewire.in", "https://thewire.in/feed", "rss", "en", "politics"),
    ("Scroll.in", "https://scroll.in", "https://scroll.in/feed", "rss", "en", "national"),
    ("Deccan Herald", "https://www.deccanherald.com", "https://www.deccanherald.com/rss", "rss", "en", "national"),
    ("News18", "https://www.news18.com", "https://www.news18.com/rss/india.xml", "rss", "en", "national"),
    ("Republic World", "https://www.republicworld.com", None, "static", "en", "national"),
    ("Dainik Bhaskar", "https://www.bhaskar.com", None, "playwright", "hi", "national"),
    ("Aaj Tak", "https://www.aajtak.in", "https://www.aajtak.in/feeds-all.xml", "rss", "hi", "national"),
    ("Dinamalar", "https://www.dinamalar.com", None, "playwright", "ta", "national"),
    ("Eenadu", "https://www.eenadu.net", None, "playwright", "te", "national"),
    ("Prajavani", "https://www.prajavani.net", None, "playwright", "kn", "national"),
    ("Business Standard", "https://www.business-standard.com", "https://www.business-standard.com/rss/latest.rss", "rss", "en", "business"),
    ("Forbes India", "https://www.forbesindia.com", None, "static", "en", "business"),
    ("India Today", "https://www.indiatoday.in", "https://www.indiatoday.in/rss/home", "rss", "en", "national"),
    ("Firstpost", "https://www.firstpost.com", "https://www.firstpost.com/rss/india.xml", "rss", "en", "national"),
    ("Sportstar", "https://sportstar.thehindu.com", "https://sportstar.thehindu.com/feeder/default.rss", "rss", "en", "sports"),
]


def seed():
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        existing_categories = session.query(Category).count()
        if existing_categories == 0:
            for name, slug, description, icon, order in CATEGORIES:
                session.add(Category(id=uuid.uuid4(), name=name, slug=slug, description=description, icon=icon, display_order=order))
            print(f"Seeded {len(CATEGORIES)} categories")
        else:
            print(f"Categories already exist ({existing_categories}), skipping")

        existing_sources = session.query(Source).count()
        if existing_sources == 0:
            for name, url, feed_url, scrape_type, language, category_slug in SOURCES:
                session.add(
                    Source(
                        id=uuid.uuid4(),
                        name=name,
                        url=url,
                        feed_url=feed_url,
                        scrape_type=scrape_type,
                        language=language,
                        category_slug=category_slug,
                    )
                )
            print(f"Seeded {len(SOURCES)} sources")
        else:
            print(f"Sources already exist ({existing_sources}), skipping")

        existing_users = session.query(User).filter_by(email="test@newssnap.ai").first()
        if existing_users is None:
            test_user_id = uuid.uuid4()
            session.add(
                User(
                    id=test_user_id,
                    email="test@newssnap.ai",
                    display_name="Test User",
                    role="admin",
                )
            )
            session.add(
                UserPreference(
                    id=uuid.uuid4(),
                    user_id=test_user_id,
                    preferred_languages="en,hi",
                    preferred_categories="technology,sports,national",
                )
            )
            print("Seeded test user (test@newssnap.ai)")
        else:
            print("Test user already exists, skipping")

        session.commit()
        print("Seed complete!")


if __name__ == "__main__":
    seed()
