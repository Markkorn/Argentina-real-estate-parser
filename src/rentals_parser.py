from __future__ import annotations

import argparse
import importlib.util
import json
import re
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin
from urllib.request import Request, urlopen

requests = None
if importlib.util.find_spec("requests"):
    import requests  # type: ignore[assignment]

BeautifulSoup = None
if importlib.util.find_spec("bs4"):
    from bs4 import BeautifulSoup  # type: ignore[assignment]


@dataclass
class Listing:
    title: str
    price: str
    location: str
    url: str
    listing_type: str
    bedrooms: int | None
    bathrooms: int | None
    area_m2: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "price": self.price,
            "location": self.location,
            "url": self.url,
            "listing_type": self.listing_type,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "area_m2": self.area_m2,
        }


@dataclass
class ParserConfig:
    base_url: str
    page_param: str
    start_page: int
    end_page: int
    local_html_path: str | None
    listing_type: str
    listings_selector: str
    title_selector: str
    price_selector: str
    location_selector: str
    url_selector: str
    url_attribute: str
    headers: dict[str, str]
    sleep_seconds: float
    output_path: str
    min_price: int | None
    max_price: int | None
    title_keywords_include: list[str]
    location_keywords_include: list[str]
    title_keywords_exclude: list[str]
    location_keywords_exclude: list[str]
    property_keywords_include: list[str]
    min_bedrooms: int | None
    max_bedrooms: int | None
    min_bathrooms: int | None
    max_bathrooms: int | None
    min_area_m2: int | None
    max_area_m2: int | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParserConfig":
        return cls(
            base_url=data["base_url"],
            page_param=data.get("page_param", "page"),
            start_page=int(data.get("start_page", 1)),
            end_page=int(data.get("end_page", 1)),
            local_html_path=data.get("local_html_path"),
            listing_type=data.get("listing_type", "rent"),
            listings_selector=data["listings_selector"],
            title_selector=data["title_selector"],
            price_selector=data["price_selector"],
            location_selector=data["location_selector"],
            url_selector=data["url_selector"],
            url_attribute=data.get("url_attribute", "href"),
            headers=data.get("headers", {}),
            sleep_seconds=float(data.get("sleep_seconds", 0)),
            output_path=data.get("output_path", "output/listings.jsonl"),
            min_price=data.get("min_price"),
            max_price=data.get("max_price"),
            title_keywords_include=[kw.lower() for kw in data.get("title_keywords_include", [])],
            location_keywords_include=[
                kw.lower() for kw in data.get("location_keywords_include", [])
            ],
            title_keywords_exclude=[kw.lower() for kw in data.get("title_keywords_exclude", [])],
            location_keywords_exclude=[
                kw.lower() for kw in data.get("location_keywords_exclude", [])
            ],
            property_keywords_include=[
                kw.lower() for kw in data.get("property_keywords_include", [])
            ],
            min_bedrooms=data.get("min_bedrooms"),
            max_bedrooms=data.get("max_bedrooms"),
            min_bathrooms=data.get("min_bathrooms"),
            max_bathrooms=data.get("max_bathrooms"),
            min_area_m2=data.get("min_area_m2"),
            max_area_m2=data.get("max_area_m2"),
        )


@dataclass
class HtmlNode:
    tag: str
    attrs: dict[str, str]
    children: list["HtmlNode"] = field(default_factory=list)
    text_chunks: list[str] = field(default_factory=list)

    def text(self) -> str:
        parts = [chunk.strip() for chunk in self.text_chunks if chunk.strip()]
        for child in self.children:
            child_text = child.text()
            if child_text:
                parts.append(child_text)
        return " ".join(parts).strip()


class SimpleHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = HtmlNode(tag="root", attrs={})
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = {key: value or "" for key, value in attrs}
        node = HtmlNode(tag=tag, attrs=attr_dict)
        self.stack[-1].children.append(node)
        self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                return

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1].text_chunks.append(data)


def parse_selector(selector: str) -> tuple[str | None, str | None]:
    selector = selector.strip()
    if not selector:
        return None, None
    if selector.startswith("."):
        return None, selector[1:]
    if "." in selector:
        tag, class_name = selector.split(".", 1)
        return tag or None, class_name or None
    return selector, None


def node_matches(node: HtmlNode, tag: str | None, class_name: str | None) -> bool:
    if tag and node.tag != tag:
        return False
    if class_name:
        classes = node.attrs.get("class", "").split()
        return class_name in classes
    return True


def find_nodes(node: HtmlNode, selector: str) -> list[HtmlNode]:
    tag, class_name = parse_selector(selector)
    matches: list[HtmlNode] = []
    for child in node.children:
        if node_matches(child, tag, class_name):
            matches.append(child)
        matches.extend(find_nodes(child, selector))
    return matches


def parse_price_amount(price_text: str) -> int | None:
    digits = re.findall(r"\d+", price_text.replace(".", "").replace(",", ""))
    if not digits:
        return None
    return int("".join(digits))


def parse_detail_value(text: str, patterns: list[str]) -> int | None:
    lowered = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1))
    return None


def parse_listing_details(text: str) -> tuple[int | None, int | None, int | None]:
    bedrooms = parse_detail_value(
        text,
        [
            r"(\d+)\s*(dormitorios|dorms|dorm|habitaciones|hab|bedrooms|beds)",
            r"(\d+)\s*(ambientes|ambientes)",
        ],
    )
    bathrooms = parse_detail_value(
        text,
        [r"(\d+)\s*(baños|banos|bathrooms|baths|bath)"],
    )
    area = parse_detail_value(
        text,
        [r"(\d+)\s*(m2|m²|mts2|mts|metros)"],
    )
    return bedrooms, bathrooms, area


def has_keywords(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def has_excluded_keywords(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def matches_price_range(price_amount: int | None, config: ParserConfig) -> bool:
    if config.min_price is None and config.max_price is None:
        return True
    if price_amount is None:
        return False
    if config.min_price is not None and price_amount < config.min_price:
        return False
    if config.max_price is not None and price_amount > config.max_price:
        return False
    return True


def matches_filters(listing: Listing, config: ParserConfig) -> bool:
    price_amount = parse_price_amount(listing.price)
    if not matches_price_range(price_amount, config):
        return False
    if not has_keywords(listing.title, config.title_keywords_include):
        return False
    if not has_keywords(listing.location, config.location_keywords_include):
        return False
    if has_excluded_keywords(listing.title, config.title_keywords_exclude):
        return False
    if has_excluded_keywords(listing.location, config.location_keywords_exclude):
        return False
    if config.property_keywords_include:
        combined_text = f"{listing.title} {listing.location}"
        if not has_keywords(combined_text, config.property_keywords_include):
            return False
    if listing.bedrooms is not None:
        if config.min_bedrooms is not None and listing.bedrooms < config.min_bedrooms:
            return False
        if config.max_bedrooms is not None and listing.bedrooms > config.max_bedrooms:
            return False
    elif config.min_bedrooms is not None or config.max_bedrooms is not None:
        return False
    if listing.bathrooms is not None:
        if config.min_bathrooms is not None and listing.bathrooms < config.min_bathrooms:
            return False
        if config.max_bathrooms is not None and listing.bathrooms > config.max_bathrooms:
            return False
    elif config.min_bathrooms is not None or config.max_bathrooms is not None:
        return False
    if listing.area_m2 is not None:
        if config.min_area_m2 is not None and listing.area_m2 < config.min_area_m2:
            return False
        if config.max_area_m2 is not None and listing.area_m2 > config.max_area_m2:
            return False
    elif config.min_area_m2 is not None or config.max_area_m2 is not None:
        return False
    return True


def build_source_configs(data: dict[str, Any]) -> list[ParserConfig]:
    if "sources" not in data:
        return [ParserConfig.from_dict(data)]

    shared: dict[str, Any] = {
        key: value
        for key, value in data.items()
        if key
        not in {
            "sources",
            "base_url",
            "page_param",
            "start_page",
            "end_page",
            "local_html_path",
            "listing_type",
            "listings_selector",
            "title_selector",
            "price_selector",
            "location_selector",
            "url_selector",
            "url_attribute",
            "headers",
            "sleep_seconds",
        }
    }
    shared_headers = data.get("headers", {})
    shared_sleep = data.get("sleep_seconds", 0)

    configs: list[ParserConfig] = []
    for source in data.get("sources", []):
        merged = {**shared, **source}
        merged["headers"] = {**shared_headers, **source.get("headers", {})}
        merged["sleep_seconds"] = source.get("sleep_seconds", shared_sleep)
        configs.append(ParserConfig.from_dict(merged))
    return configs


def load_config(path: Path) -> list[ParserConfig]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return build_source_configs(data)


def build_page_url(base_url: str, page_param: str, page: int) -> tuple[str, dict[str, Any]]:
    return base_url, {page_param: page}


def parse_listings(html: str, config: ParserConfig) -> Iterable[Listing]:
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(config.listings_selector)
        for card in cards:
            title_node = card.select_one(config.title_selector)
            price_node = card.select_one(config.price_selector)
            location_node = card.select_one(config.location_selector)
            title = title_node.get_text(strip=True) if title_node else ""
            price = price_node.get_text(strip=True) if price_node else ""
            location = location_node.get_text(strip=True) if location_node else ""
            link = card.select_one(config.url_selector)
            href = ""
            if link is not None:
                href = link.get(config.url_attribute, "")
            url = urljoin(config.base_url, href)
            if title or price or location or url:
                bedrooms, bathrooms, area_m2 = parse_listing_details(
                    f"{title} {location}"
                )
                yield Listing(
                    title=title,
                    price=price,
                    location=location,
                    url=url,
                    listing_type=config.listing_type,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    area_m2=area_m2,
                )
        return

    parser = SimpleHtmlParser()
    parser.feed(html)
    cards = find_nodes(parser.root, config.listings_selector)
    for card in cards:
        title_node = next(iter(find_nodes(card, config.title_selector)), None)
        price_node = next(iter(find_nodes(card, config.price_selector)), None)
        location_node = next(iter(find_nodes(card, config.location_selector)), None)
        link_node = next(iter(find_nodes(card, config.url_selector)), None)
        title = title_node.text() if title_node else ""
        price = price_node.text() if price_node else ""
        location = location_node.text() if location_node else ""
        href = link_node.attrs.get(config.url_attribute, "") if link_node else ""
        url = urljoin(config.base_url, href)
        if title or price or location or url:
            bedrooms, bathrooms, area_m2 = parse_listing_details(f"{title} {location}")
            yield Listing(
                title=title,
                price=price,
                location=location,
                url=url,
                listing_type=config.listing_type,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                area_m2=area_m2,
            )


def fetch_page(session: Any, url: str, params: dict[str, Any]) -> str:
    if requests is not None:
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.text
    query = "&".join(f"{key}={value}" for key, value in params.items())
    full_url = f"{url}?{query}" if query else url
    request = Request(full_url, headers=getattr(session, "headers", {}))
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def write_listings(path: Path, listings: Iterable[Listing], config: ParserConfig) -> int:
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for listing in listings:
            if matches_filters(listing, config):
                handle.write(json.dumps(listing.to_dict(), ensure_ascii=False) + "\n")
                count += 1
    return count


def run_parser(config: ParserConfig) -> int:
    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if config.local_html_path:
        html = Path(config.local_html_path).read_text(encoding="utf-8")
        listings = list(parse_listings(html, config))
        return write_listings(output_path, listings, config)

    session: Any = None
    if requests is not None:
        session = requests.Session()
        if config.headers:
            session.headers.update(config.headers)
    else:
        session = type("SimpleSession", (), {"headers": config.headers})()

    total = 0
    for page in range(config.start_page, config.end_page + 1):
        url, params = build_page_url(config.base_url, config.page_param, page)
        html = fetch_page(session, url, params)
        listings = list(parse_listings(html, config))
        total += write_listings(output_path, listings, config)
        if config.sleep_seconds:
            time.sleep(config.sleep_seconds)
    return total


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parser for Argentina rental listings. Configure selectors in a JSON file "
            "to match the target website's HTML structure."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/example_config.json"),
        help="Path to JSON config with selectors and crawl settings.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    configs = load_config(args.config)
    total = 0
    output_paths = set()
    for config in configs:
        total += run_parser(config)
        output_paths.add(config.output_path)
    outputs = ", ".join(sorted(output_paths))
    print(f"Saved {total} listings to {outputs}")


if __name__ == "__main__":
    main()
