import re
import ast
from typing import Optional, Any, List, Dict

from .logging_utils import _log
from .models import ProductMemory, SearchIntent


_KNOWN_BRANDS = {
    "western digital": "Western Digital",
    "lenovo": "Lenovo",
    "dell": "Dell",
    "hpe": "HPE",
    "hp": "HP",
    "asus": "ASUS",
    "synology": "Synology",
    "seagate": "Seagate",
    "supermicro": "Supermicro",
    "intel": "Intel",
    "amd": "AMD",
    "wd": "WD",
}

_PRODUCT_TYPE_PATTERNS = [
    (r"\b(laptop|notebook|ultrabook)\b", "laptop"),
    (r"\b(may chu|máy chu|server|rack server)\b", "máy chủ"),
    (r"\b(o cung ngoai|ổ cứng ngoài|external hdd|external drive)\b", "ổ cứng ngoài"),
    (r"\b(nas)\b", "nas"),
    (r"\b(workstation)\b", "workstation"),
    (r"\b(thiet bi mang|thiết bị mạng|network device|switch|router|firewall)\b", "thiết bị mạng"),
]

_PRICE_SKIP_KEYWORDS = [
    "liên hệ",
    "báo giá",
    "tbd",
    "n/a",
    "unknown",
    "chưa có",
    "cập nhật",
    "liên lạc",
]

_UNIT_ALIASES = {
    "trieu": "triệu",
    "tr": "triệu",
    "m": "triệu",
    "ty": "tỷ",
    "b": "tỷ",
    "nghin": "nghìn",
    "k": "k",
    "vnd": "vnd",
    "dong": "dong",
    "đ": "đ",
}

_PRICE_TYPO_REPLACEMENTS = {
    "triueej": "triệu",
    "trieeuj": "triệu",
    "trieuj": "triệu",
    "triueu": "triệu",
    "triu": "triệu",
}

_QUERY_TYPO_REPLACEMENTS = {
    "laptpo": "laptop",
    "latop": "laptop",
    "laptob": "laptop",
    "giaa": "gia",
    "duoii": "duoi",
    "trieeeu": "trieu",
    "triue": "trieu",
}


def _normalize_query_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _normalize_user_query(text: str) -> str:
    """Normalize common typos / no-diacritic variants for more robust intent parsing."""
    normalized = _normalize_query_text(text).lower()

    for typo, canonical in _QUERY_TYPO_REPLACEMENTS.items():
        normalized = re.sub(rf"(?<!\w){re.escape(typo)}(?!\w)", canonical, normalized)

    for typo, canonical in _PRICE_TYPO_REPLACEMENTS.items():
        normalized = re.sub(rf"(?<!\w){re.escape(typo)}(?!\w)", canonical, normalized)

    # Normalize common ASCII Vietnamese forms used in search queries.
    normalized = re.sub(r"(?<!\w)duoi(?!\w)", "dưới", normalized)
    normalized = re.sub(r"(?<!\w)tren(?!\w)", "trên", normalized)
    normalized = re.sub(r"(?<!\w)toi\s*da(?!\w)", "tối đa", normalized)
    normalized = re.sub(r"(?<!\w)toi\s*thieu(?!\w)", "tối thiểu", normalized)
    normalized = re.sub(r"(?<!\w)nho\s*hon(?!\w)", "nhỏ hơn", normalized)
    normalized = re.sub(r"(?<!\w)thap\s*hon(?!\w)", "thấp hơn", normalized)
    normalized = re.sub(r"(?<!\w)lon\s*hon(?!\w)", "lớn hơn", normalized)
    normalized = re.sub(r"(?<!\w)it\s*nhat(?!\w)", "ít nhất", normalized)
    normalized = re.sub(r"(?<!\w)trieu(?!\w)", "triệu", normalized)

    return _normalize_query_text(normalized)


def _normalize_price_query_text(text: str) -> str:
    normalized = _normalize_user_query(text)
    for typo, canonical in _PRICE_TYPO_REPLACEMENTS.items():
        normalized = re.sub(rf"(?<!\w){re.escape(typo)}(?!\w)", canonical, normalized)
    return normalized


def _normalize_unit_token(unit_text: Optional[str]) -> str:
    unit = (unit_text or "").strip().lower().strip(".,:;!?")
    if not unit:
        return ""

    if unit in _UNIT_ALIASES:
        return _UNIT_ALIASES[unit]

    if unit.startswith("tri"):
        return "triệu"
    if unit.startswith("ty") or unit.startswith("tỷ"):
        return "tỷ"
    if unit.startswith("ngh"):
        return "nghìn"

    return unit


def _extract_known_brand(query: str) -> Optional[str]:
    query_lower = _normalize_query_text(query).lower()
    for needle, canonical in sorted(_KNOWN_BRANDS.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", query_lower):
            return canonical
    return None


def _extract_product_type(query: str) -> Optional[str]:
    query_lower = _normalize_query_text(query).lower()
    for pattern, canonical in _PRODUCT_TYPE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return canonical
    return None


def _price_token_to_vnd(amount_text: str, unit_text: Optional[str]) -> Optional[int]:
    raw_amount = str(amount_text).strip()

    # Thousands-grouped numbers: 24,771,000 or 24.771.000
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", raw_amount):
        value = float(int(re.sub(r"[.,]", "", raw_amount)))
    # Mixed separators usually represent grouped integers too.
    elif "," in raw_amount and "." in raw_amount:
        value = float(int(re.sub(r"[.,]", "", raw_amount)))
    # Comma-only may be decimal or grouping.
    elif "," in raw_amount:
        if raw_amount.count(",") > 1 or re.fullmatch(r"\d{1,3}(,\d{3})+", raw_amount):
            value = float(int(raw_amount.replace(",", "")))
        else:
            try:
                value = float(raw_amount.replace(",", "."))
            except (TypeError, ValueError):
                return None
    # Dot-only may be decimal or grouping.
    elif "." in raw_amount:
        if raw_amount.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", raw_amount):
            value = float(int(raw_amount.replace(".", "")))
        else:
            try:
                value = float(raw_amount)
            except (TypeError, ValueError):
                return None
    else:
        try:
            value = float(raw_amount)
        except (TypeError, ValueError):
            return None

    unit = _normalize_unit_token(unit_text)
    multiplier = 1
    if unit in {"tỷ", "ty", "b"}:
        multiplier = 1_000_000_000
    elif unit in {"triệu", "trieu", "tr", "m"}:
        multiplier = 1_000_000
    elif unit in {"k", "nghìn", "nghin"}:
        multiplier = 1_000
    elif unit in {"vnd", "đ", "dong"}:
        multiplier = 1

    return int(value * multiplier)


def _extract_amount_from_text(text: str) -> Optional[int]:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹđ]+)?", text, re.IGNORECASE)
    if not match:
        return None
    return _price_token_to_vnd(match.group(1), match.group(2))


def _parse_structured_price_range(price_range: Any) -> tuple[Optional[int], Optional[int]]:
    if price_range is None:
        return None, None

    data: Any = price_range
    if isinstance(price_range, str):
        raw = price_range.strip()
        if not raw:
            return None, None
        try:
            data = ast.literal_eval(raw)
        except Exception:
            data = raw

    if isinstance(data, dict):
        min_raw = data.get("min", data.get("gte", data.get("gt")))
        max_raw = data.get("max", data.get("lte", data.get("lt")))

        min_v = _price_token_to_vnd(str(min_raw), None) if min_raw is not None else None
        max_v = _price_token_to_vnd(str(max_raw), None) if max_raw is not None else None
        return min_v, max_v

    text = _normalize_price_query_text(str(data))
    min_match = re.search(r"\b(?:min|gte|gt)\b\s*[:=]\s*(\d[\d.,]*)", text)
    max_match = re.search(r"\b(?:max|lte|lt)\b\s*[:=]\s*(\d[\d.,]*)", text)
    min_v = _price_token_to_vnd(min_match.group(1), None) if min_match else None
    max_v = _price_token_to_vnd(max_match.group(1), None) if max_match else None
    return min_v, max_v


def _to_intent_price_vnd(amount_text: str, unit_text: Optional[str]) -> Optional[int]:
    parsed = _price_token_to_vnd(amount_text, unit_text)
    if parsed is None:
        return None

    normalized_unit = _normalize_unit_token(unit_text)
    if not normalized_unit and 0 < parsed <= 1000:
        return parsed * 1_000_000

    return parsed


def _parse_price_intent(text: str) -> tuple[Optional[int], Optional[int]]:
    query = _normalize_price_query_text(text)
    if not query:
        return None, None

    range_match = re.search(
        r"(?:từ|from)?\s*(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹđ]+)?\s*(?:đến|tới|to|\-|~|và)\s*(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹđ]+)?",
        query,
        re.IGNORECASE,
    )
    if range_match:
        price_min = _to_intent_price_vnd(range_match.group(1), range_match.group(2))
        price_max = _to_intent_price_vnd(range_match.group(3), range_match.group(4))
        if price_min is not None and price_max is not None:
            return min(price_min, price_max), max(price_min, price_max)

    upper_patterns = [
        r"(?:dưới|<=|không quá|tối đa|nhỏ hơn|thấp hơn)\s*(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹđ]+)?",
        r"(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹđ]+)?\s*(?:trở xuống|or less)",
    ]
    for pattern in upper_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return None, _to_intent_price_vnd(match.group(1), match.group(2))

    lower_patterns = [
        r"(?:trên|>=|lớn hơn|ít nhất|tối thiểu)\s*(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹđ]+)?",
        r"(\d+(?:[.,]\d+)?)\s*([a-zA-ZÀ-ỹđ]+)?\s*(?:trở lên|or more)",
    ]
    for pattern in lower_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return _to_intent_price_vnd(match.group(1), match.group(2)), None

    return None, None


def _build_search_intent(memory: ProductMemory, base_query: str, effective_query: str) -> SearchIntent:
    combined_query = _normalize_query_text(" ".join(part for part in [base_query, effective_query] if part))
    structured_price_min, structured_price_max = _parse_structured_price_range(memory.price_range)
    text_price_min, text_price_max = _parse_price_intent(" ".join(part for part in [str(memory.price_range or ""), combined_query] if part))
    price_min = structured_price_min if structured_price_min is not None else text_price_min
    price_max = structured_price_max if structured_price_max is not None else text_price_max

    return SearchIntent(
        product_type=memory.product_type or _extract_product_type(combined_query),
        brand=memory.brand or _extract_known_brand(combined_query),
        series=memory.series,
        model=memory.model,
        price_min=price_min,
        price_max=price_max,
        price_text=memory.price_range or (combined_query if price_min is not None or price_max is not None else None),
    )


def _build_metadata_filter_clauses(intent: SearchIntent, column_map: Dict[str, List[str]]) -> tuple[List[str], List[Any]]:
    clauses: List[str] = []
    params: List[Any] = []

    for field_name, columns in column_map.items():
        value = getattr(intent, field_name, None)
        if not value:
            continue

        params.append(f"%{value}%")
        param_index = len(params)
        if len(columns) == 1:
            clauses.append(f"{columns[0]} ILIKE ${param_index}")
        else:
            clauses.append("(" + " OR ".join(f"{column} ILIKE ${param_index}" for column in columns) + ")")

    return clauses, params


def _parse_price_text_to_vnd(price_text: Any) -> Optional[int]:
    low_value, high_value = _extract_price_bounds_to_vnd(price_text)
    if high_value is not None:
        return high_value
    return low_value


def _extract_price_bounds_to_vnd(price_text: Any) -> tuple[Optional[int], Optional[int]]:
    if price_text is None:
        return None, None

    normalized = _normalize_query_text(str(price_text)).lower()
    if not normalized:
        return None, None

    if any(keyword in normalized for keyword in _PRICE_SKIP_KEYWORDS):
        return None, None

    amount_matches = re.findall(
        r"(\d[\d.,]*)\s*(tỷ|ty|b|triệu|trieu|tr|m|k|nghìn|nghin|vnd|đ|dong)?",
        normalized,
        re.IGNORECASE,
    )
    if not amount_matches:
        return None, None

    values: List[int] = []
    for amount_text, unit_text in amount_matches:
        value = _price_token_to_vnd(amount_text, unit_text)
        if value is not None and value > 0:
            values.append(value)

    if not values:
        return None, None

    return min(values), max(values)


def _is_price_comparison_query(query: str) -> bool:
    query_lower = _normalize_user_query(query)
    price_patterns = [
        r"dưới\s+\d+",
        r"duoi\s+\d+",
        r"từ\s+\d+.*đến\s+\d+",
        r"từ\s+\d+.*tới\s+\d+",
        r"tu\s+\d+.*den\s+\d+",
        r"tu\s+\d+.*toi\s+\d+",
        r"\d+.*triệu\s+trở\s+lên",
        r"\d+.*trieu\s+tro\s+len",
        r"rẻ\s+hơn\s+\d+",
        r"đắt\s+hơn\s+\d+",
        r"giá.*dưới",
        r"gia.*duoi",
        r"giá.*tối\s+đa",
        r"gia.*toi\s+da",
        r"giá.*tối\s+thiểu",
        r"gia.*toi\s+thieu",
        r"so\s+sánh.*giá",
        r"so\s+sanh.*gia",
        r"giá\s+rẻ|rẻ\s+hơn",
        r"gia\s+re|re\s+hon",
    ]

    for pattern in price_patterns:
        if re.search(pattern, query_lower):
            return True

    return False


def _filter_products_with_specific_price(products: List[Dict]) -> List[Dict]:
    filtered = []
    for product in products:
        price = str(product.get("giá", "")).strip().lower()

        should_skip = False
        for keyword in _PRICE_SKIP_KEYWORDS:
            if keyword in price:
                should_skip = True
                break

        if should_skip:
            continue

        if re.search(r"\d+", price):
            filtered.append(product)

    return filtered


def _deduplicate_products(products: List[Dict]) -> List[Dict]:
    seen_names = set()
    deduplicated = []

    for product in products:
        product_name = (product.get("tên") or "").strip().lower()
        if not product_name:
            deduplicated.append(product)
            continue

        if product_name not in seen_names:
            seen_names.add(product_name)
            deduplicated.append(product)

    return deduplicated


def _product_matches_text_intent(product: Dict, intent: SearchIntent) -> bool:
    product_name = str(product.get("tên") or product.get("id") or "N/A")
    fields_to_check = [
        product.get("tên"),
        product.get("hãng"),
        product.get("cấu_hình"),
        product.get("description"),
        product.get("config"),
        product.get("text"),
    ]
    searchable_text = _normalize_query_text(" ".join(str(value or "") for value in fields_to_check)).lower()

    for value in [intent.brand, intent.series, intent.model]:
        if value and value.lower() not in searchable_text:
            _log("INTENT_FILTER", f"reject '{product_name}': missing token '{value}'")
            return False

    if intent.price_min is None and intent.price_max is None:
        _log("INTENT_FILTER", f"pass '{product_name}': no price constraint")
        return True

    product_price_raw = product.get("giá")
    product_price_min, product_price_max = _extract_price_bounds_to_vnd(product_price_raw)
    _log(
        "INTENT_FILTER",
        (
            f"price_check '{product_name}': raw_price='{product_price_raw}', "
            f"parsed_min={product_price_min}, parsed_max={product_price_max}, "
            f"intent_min={intent.price_min}, intent_max={intent.price_max}"
        ),
    )

    if product_price_min is None and product_price_max is None:
        _log("INTENT_FILTER", f"reject '{product_name}': cannot parse product price")
        return False

    if intent.price_min is not None and (product_price_max is None or product_price_max < intent.price_min):
        _log("INTENT_FILTER", f"reject '{product_name}': price below intent minimum")
        return False
    if intent.price_max is not None and (product_price_min is None or product_price_min > intent.price_max):
        _log("INTENT_FILTER", f"reject '{product_name}': price above intent maximum")
        return False

    _log("INTENT_FILTER", f"pass '{product_name}': price constraints satisfied")
    return True


def _filter_products_by_intent(products: List[Dict], intent: SearchIntent) -> List[Dict]:
    if not products:
        return products

    filtered = [product for product in products if _product_matches_text_intent(product, intent)]
    return filtered
