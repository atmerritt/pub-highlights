from urllib.request import urlopen
from datetime import datetime, timedelta
from typing import cast
import feedparser


def format_datetime(dt: datetime) -> str:
    """Format an individual datetime as expected by the arXiv API."""
    # Convert to timetuple for easier iteration
    timetup = dt.timetuple()

    # Required: year, month, day, hour, minute, second (6 terms)
    formatted_time = "".join([str(timetup[i]).zfill(2) for i in range(6)])

    return formatted_time


def construct_date_range(window_days: int = 3) -> str:
    """Construct a date range, formatted as expected by the arXiv API."""
    # End of date range: now
    end_time = datetime.now()

    # Start of date range: <window_days> ago, rounded down to the beginning of the day
    start_time = end_time - timedelta(days=window_days)
    start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)

    formatted_date_range = (
        f"[{format_datetime(start_time)}+TO+{format_datetime(end_time)}]"
    )
    return formatted_date_range


def construct_arxiv_query(
    search_query: str, window_days: int = 3, max_results: int = 100
) -> str:
    """Construct the query for the arXiv API."""
    api_request_url = "http://export.arxiv.org/api/query?search_query="

    # Update query with search terms
    search_query_terms = search_query.split(" ")
    for i, query in enumerate(search_query_terms):
        query_str = f"all:{query.replace(' ', '+')}"
        if i < len(search_query_terms) - 1:
            query_str += "+AND+"
        api_request_url += query_str

    # Focus on recent publications
    api_request_url += (
        f"+AND+submittedDate:{construct_date_range(window_days=window_days)}"
    )

    # Impose a maximum number of results
    api_request_url += f"&max_results={max_results}"
    return api_request_url


def call_arxiv_api(
    search_query: str, window_days: int = 3, max_results: int = 100
) -> list[dict[str, str]]:
    """
    Call the arXiv API.

    The search query is the string to search for. This can be a single word (e.g. "PSF"),
    or a phrase (e.g. "low surface brightness"). It can also be one or more subject classification,
    e.g. astro-ph.CO or astro-ph.GA or cs.CV.

    The API is designed to only return one page of results at once. It is therefore advisable to
    set max_results high enough that we get all relevant papers in one go. Note - this tool is
    designed to help researchers catch up on *recent* results, not everything that has happened in
    the last 6 months, so setting window_days appropriately should take care of this as well.
    """
    # Set up request URL
    api_request_url = construct_arxiv_query(
        search_query=search_query, window_days=window_days, max_results=max_results
    )

    # Call the arxiv API
    with urlopen(api_request_url) as url:
        xml_results = url.read()

    # Parse results and focus on the "entries" field
    parsed_pubs = feedparser.parse(xml_results)
    return cast(list[dict[str, str]], parsed_pubs["entries"])


def clean_results(publist: feedparser.util.FeedParserDict) -> list[dict[str, str]]:
    """Clean up the metadata.

    * Select which fields to keep, renaming a few as needed
    * Shorten the author list to only the first author
    * Fix some formatting issues in the paper title
    """
    clean_pub_details: list[dict[str, str]] = []
    for pub in publist:
        pub = dict(pub)
        d = {
            "title": pub["title"].replace("\n", "").replace("  ", " "),
            "author": pub["authors"][0]["name"],
            "link": pub["link"],
            "text": pub["summary"],
            "category": ", ".join([t["term"] for t in pub["tags"]]),
            "published": pub["published"],
            "updated": pub["updated"],
        }
        clean_pub_details.append(d)

    return sorted(clean_pub_details, key=lambda d: d["updated"])[::-1]
