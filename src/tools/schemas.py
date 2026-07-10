"""Tool argument schemas for search-related tools."""

from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator, model_validator


class SearchProductsArgs(BaseModel):
    """Schema tham số cho tool search_products."""

    user_query: str = Field(default="", description="Câu người dùng gõ nguyên văn. Nếu để trống, tự động tổng hợp từ các structured fields.")
    max_results: int = Field(default=20, description="Số lượng kết quả tối đa (mặc định 20).")
    product_type: Optional[str] = Field(default=None, description='Loại thiết bị. VD: "ổ cứng ngoài", "máy chủ", "laptop".')
    brand: Optional[str] = Field(default=None, description='Hãng sản xuất. VD: "WD", "Dell", "HPE", "Synology".')
    series: Optional[str] = Field(default=None, description='Dòng sản phẩm. VD: "My Book", "PowerEdge", "ThinkPad".')
    model: Optional[str] = Field(default=None, description='Model cụ thể. VD: "R740xd", "DS223j", "1381".')
    cpu: Optional[str] = Field(default=None, description='CPU. VD: "Gold 6248", "E-2434".')
    ram: Optional[str] = Field(default=None, description='RAM. VD: "128GB", "32GB ECC".')
    storage: Optional[str] = Field(default=None, description='Lưu trữ gắn trong. VD: "2TB SSD".')
    capacity: Optional[str] = Field(default=None, description='Dung lượng ổ cứng ngoài / NAS. VD: "3TB", "8TB".')
    interface: Optional[str] = Field(default=None, description='Giao tiếp. VD: "USB 3.0", "PCIe 4.0".')
    price_range: Optional[str] = Field(default=None, description='Khoảng giá. VD: "dưới 5 triệu", "10-20 triệu".')
    product_link: Optional[str] = Field(default=None, description='Link sản phẩm. VD: "https://example.com/product/123".')

    @field_validator("user_query", mode="before")
    @classmethod
    def _empty_user_query_to_str(cls, value: Any) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            return ""
        return str(value)

    @model_validator(mode="after")
    def _fill_user_query(self) -> "SearchProductsArgs":
        if not self.user_query.strip():
            tokens = [
                value for value in [
                    self.product_type,
                    self.brand,
                    self.series,
                    self.model,
                    self.cpu,
                    self.ram,
                    self.storage,
                    self.capacity,
                    self.interface,
                    self.price_range,
                ]
                if value
            ]
            self.user_query = " ".join(tokens) if tokens else "(unknown)"
        return self

    @field_validator("max_results", mode="before")
    @classmethod
    def _coerce_max_results(cls, value: Any) -> int:
        if value is None or (isinstance(value, str) and not value.strip()):
            return 5
        try:
            return int(value)
        except (TypeError, ValueError):
            return 5

    @field_validator("price_range", mode="before")
    @classmethod
    def _normalize_price_range(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            min_raw = value.get("min", value.get("gte", value.get("gt")))
            max_raw = value.get("max", value.get("lte", value.get("lt")))
            parts = []
            if min_raw is not None:
                parts.append(f"min={min_raw}")
            if max_raw is not None:
                parts.append(f"max={max_raw}")
            return " ".join(parts) if parts else str(value)
        return value

    @field_validator(
        "product_type",
        "brand",
        "series",
        "model",
        "cpu",
        "ram",
        "storage",
        "capacity",
        "interface",
        "price_range",
        "product_link",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value
