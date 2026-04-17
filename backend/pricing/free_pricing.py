from __future__ import annotations

import time
from dataclasses import dataclass

import requests


@dataclass
class PriceOffer:
    cloud: str
    region: str
    instance_type: str
    price_hour_usd: float
    source: str
    fetched_at: float


_CACHE: dict[str, tuple[float, list[PriceOffer]]] = {}
_TTL_SECONDS = 3600


def _cached(key: str) -> list[PriceOffer] | None:
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if (time.time() - ts) > _TTL_SECONDS:
        return None
    return value


def _set_cache(key: str, offers: list[PriceOffer]) -> list[PriceOffer]:
    _CACHE[key] = (time.time(), offers)
    return offers


def _azure_public_prices() -> list[PriceOffer]:
    key = "azure"
    cached = _cached(key)
    if cached is not None:
        return cached

    query = (
        "https://prices.azure.com/api/retail/prices"
        "?$filter=serviceName eq 'Virtual Machines' and armRegionName eq 'westeurope'"
        " and priceType eq 'Consumption' and contains(skuName, 'D4s v5')"
    )
    offers: list[PriceOffer] = []
    try:
        response = requests.get(query, timeout=6)
        response.raise_for_status()
        items = (response.json() or {}).get("Items", [])
        for item in items:
            meter_name = str(item.get("meterName", ""))
            if "Spot" in meter_name:
                continue
            unit_price = item.get("unitPrice")
            if unit_price is None:
                continue
            offers.append(
                PriceOffer(
                    cloud="azure",
                    region=str(item.get("armRegionName", "westeurope")),
                    instance_type=str(item.get("armSkuName", "Standard_D4s_v5")),
                    price_hour_usd=float(unit_price),
                    source="azure_retail_api",
                    fetched_at=time.time(),
                )
            )
            break
    except Exception:
        offers = []

    if not offers:
        offers = [
            PriceOffer(
                cloud="azure",
                region="westeurope",
                instance_type="Standard_D4s_v5",
                price_hour_usd=0.24,
                source="fallback_snapshot",
                fetched_at=time.time(),
            )
        ]

    return _set_cache(key, offers)


def _aws_public_prices() -> list[PriceOffer]:
    key = "aws"
    cached = _cached(key)
    if cached is not None:
        return cached

    # Public endpoint without credentials. Kept lightweight with fallback.
    offers: list[PriceOffer] = []
    try:
        # region index is small and public; use as liveness check.
        index_url = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/region_index.json"
        response = requests.get(index_url, timeout=6)
        response.raise_for_status()
        if response.json().get("regions"):
            offers.append(
                PriceOffer(
                    cloud="aws",
                    region="eu-west-1",
                    instance_type="m6i.xlarge",
                    price_hour_usd=0.192,
                    source="aws_public_offer_index+snapshot",
                    fetched_at=time.time(),
                )
            )
    except Exception:
        offers = []

    if not offers:
        offers = [
            PriceOffer(
                cloud="aws",
                region="eu-west-1",
                instance_type="m6i.xlarge",
                price_hour_usd=0.192,
                source="fallback_snapshot",
                fetched_at=time.time(),
            )
        ]

    return _set_cache(key, offers)


def _gcp_free_snapshot() -> list[PriceOffer]:
    key = "gcp"
    cached = _cached(key)
    if cached is not None:
        return cached

    offers = [
        PriceOffer(
            cloud="gcp",
            region="europe-west4",
            instance_type="n2-standard-4",
            price_hour_usd=0.18,
            source="public_snapshot",
            fetched_at=time.time(),
        )
    ]
    return _set_cache(key, offers)


def get_free_cross_cloud_offers() -> list[PriceOffer]:
    return [*_aws_public_prices(), *_azure_public_prices(), *_gcp_free_snapshot()]
