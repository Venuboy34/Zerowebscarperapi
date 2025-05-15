from fastapi import FastAPI, HTTPException, Query
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from mangum import Mangum

app = FastAPI()

MAX_TOTAL_SIZE = 150000  # max combined size of HTML+CSS+JS

def validate_url(url: str) -> bool:
    return url.startswith(('http://', 'https://'))

def fetch_url_content(url: str, headers: dict, timeout: int = 10) -> str:
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text

@app.get("/scrape")
def scrape_all(url: str = Query(..., description="URL to scrape HTML, CSS, JS from")):
    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL. Use http:// or https://")

    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        html = fetch_url_content(url, headers)
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching URL: {str(e)}")

    soup = BeautifulSoup(html, "html.parser")

    total_size = len(html)
    if total_size > MAX_TOTAL_SIZE:
        html = html[:MAX_TOTAL_SIZE]

    css_files = []
    for link_tag in soup.find_all("link", rel="stylesheet"):
        href = link_tag.get("href")
        if href:
            css_url = urljoin(url, href)
            try:
                css_content = fetch_url_content(css_url, headers)
                if total_size + len(css_content) > MAX_TOTAL_SIZE:
                    break
                total_size += len(css_content)
                css_files.append({"url": css_url, "content": css_content})
            except requests.RequestException:
                continue

    js_files = []
    for script_tag in soup.find_all("script"):
        src = script_tag.get("src")
        script_content = ""
        if src:
            js_url = urljoin(url, src)
            try:
                js_content = fetch_url_content(js_url, headers)
                if total_size + len(js_content) > MAX_TOTAL_SIZE:
                    break
                total_size += len(js_content)
                script_content = js_content
            except requests.RequestException:
                continue
        else:
            script_content = script_tag.string or ""
            if total_size + len(script_content) > MAX_TOTAL_SIZE:
                break
            total_size += len(script_content)

        js_files.append({"src": src or "inline", "content": script_content})

    return {
        "url": url,
        "html": html,
        "css_files": css_files,
        "js_files": js_files,
        "total_fetched_size": total_size
    }

handler = Mangum(app)
