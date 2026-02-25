from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from bson import ObjectId


def _round_price(v: float) -> float:
    if v < 0:
        raise ValueError("Ціна не може бути від'ємною")
    return round(v, 2)


class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info=None):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")


# Project models
class ProjectCreate(BaseModel):
    name: str
    sort_order: int = 0


class Project(ProjectCreate):
    id: Optional[str] = Field(None, alias="_id")

    class Config:
        populate_by_name = True


# Category models
class CategoryCreate(BaseModel):
    name: str
    icon: str = "tag"
    sort_order: int = 0
    project_id: Optional[str] = None


class Category(CategoryCreate):
    id: Optional[str] = Field(None, alias="_id")

    class Config:
        populate_by_name = True


# Modifier models
class ModifierOption(BaseModel):
    name: str
    price_add: float = 0  # Additional price for this option

    @field_validator('price_add')
    @classmethod
    def round_price_add(cls, v):
        return _round_price(v)


class ModifierGroupCreate(BaseModel):
    name: str  # e.g., "Розмір", "Молоко", "Добавки"
    type: str = "single"  # single (radio) or multiple (checkbox)
    required: bool = False
    options: List[ModifierOption] = []
    # New fields for enhanced modifiers
    display_order: int = 0  # Order of display (1, 2, 3...)
    display_mode: str = "row"  # "row" or "column"
    show_for_otp: bool = True  # Show for OTP (Order Taking Point)
    show_for_vtp: bool = True  # Show for VTP (Verification Terminal Point)
    is_enabled: bool = True  # Enable/disable without deleting


class ModifierGroup(ModifierGroupCreate):
    id: Optional[str] = Field(None, alias="_id")

    class Config:
        populate_by_name = True


# Product Tag models
class ProductTagCreate(BaseModel):
    name: str
    color: str = "#6366f1"


class ProductTag(ProductTagCreate):
    id: Optional[str] = Field(None, alias="_id")

    class Config:
        populate_by_name = True


# Audit Log model
class AuditLog(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    action: str  # "create", "update", "delete", "copy"
    entity_type: str  # "product", "modifier", "category", "order"
    entity_id: str
    entity_name: str
    changes: dict = {}  # {"field": {"old": x, "new": y}}
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Project model for organizing assortments
class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    is_active: bool = True


class Project(ProjectCreate):
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Product models
class ProductCreate(BaseModel):
    name: str
    category_id: str
    price: float
    description: str = ""
    image: str = "/static/img/placeholder.svg"
    weight: str = ""
    cook_time: str = ""
    available: bool = True
    modifier_groups: List[str] = []  # List of modifier group IDs
    daily_production_norm: Optional[int] = None  # Daily production target
    tags: List[str] = []  # List of tag IDs
    is_alcohol: bool = False  # Alcohol indicator
    project_id: Optional[str] = None  # Project for organization

    @field_validator('price')
    @classmethod
    def round_price(cls, v):
        return _round_price(v)


class Product(ProductCreate):
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Selected modifier for order
class SelectedModifier(BaseModel):
    group_name: str
    option_name: str
    price_add: float = 0

    @field_validator('price_add')
    @classmethod
    def round_price_add(cls, v):
        return _round_price(v)


# Order item
class OrderItem(BaseModel):
    product_id: str
    name: str
    qty: int = 1
    price: float
    modifiers: List[SelectedModifier] = []
    is_combo: bool = False
    combo_items: Optional[List[dict]] = None  # Expanded items for kitchen display

    @field_validator('price')
    @classmethod
    def round_price(cls, v):
        return _round_price(v)


# Order models
class OrderCreate(BaseModel):
    items: List[OrderItem]
    order_type: str = "dine_in"  # dine_in, takeaway, delivery, self_service
    table_number: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    # New delivery fields
    delivery_address: Optional[str] = None
    delivery_zone_id: Optional[str] = None
    delivery_fee: float = 0  # Passed from frontend for transparency
    notes: Optional[str] = None
    promo_code: Optional[str] = None
    customer_discount_percent: Optional[float] = None
    payment_method: str = "cash"  # cash, card, online

    @field_validator('delivery_fee')
    @classmethod
    def round_delivery_fee(cls, v):
        return _round_price(v)


class Order(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    order_number: str
    items: List[OrderItem]
    total: float
    status: str = "new"  # new, preparing, ready, completed, cancelled
    payment_status: str = "pending"  # pending, paid
    payment_method: str = "cash"  # cash, card, online
    order_type: str = "dine_in"  # dine_in, takeaway, delivery, self_service
    table_number: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    # New delivery fields
    delivery_address: Optional[str] = None
    delivery_zone_id: Optional[str] = None
    delivery_zone_name: Optional[str] = None
    delivery_fee: float = 0
    card_surcharge_percent: float = 0
    card_surcharge_amount: float = 0
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Stats models
class DailyStat(BaseModel):
    date: str
    orders_count: int
    revenue: float


class Stats(BaseModel):
    today_orders: int = 0
    today_revenue: float = 0
    pending_orders: int = 0
    completed_orders: int = 0
    top_products: List[dict] = []
    daily_stats: List[DailyStat] = []


# Feedback models
class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)  # 1-5 stars, required
    phone: str = ""
    comment: str = ""


class Feedback(FeedbackCreate):
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Combo item
class ComboItem(BaseModel):
    product_id: str
    product_name: str
    qty: int = 1


# Combo models
class ComboCreate(BaseModel):
    name: str
    description: str = ""
    image: str = "/static/img/placeholder.svg"
    items: List[ComboItem] = []
    regular_price: float  # Sum of individual items
    combo_price: float  # Discounted price
    available: bool = True

    @field_validator('regular_price', 'combo_price')
    @classmethod
    def round_prices(cls, v):
        return _round_price(v)


class Combo(ComboCreate):
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Promo code models
class PromoCodeCreate(BaseModel):
    code: str
    discount_type: str = "percentage"  # percentage or fixed
    discount_value: float
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    usage_limit: Optional[int] = None  # None = unlimited
    min_order_amount: float = 0
    is_active: bool = True

    @field_validator('discount_value', 'min_order_amount')
    @classmethod
    def round_promo_amounts(cls, v):
        return _round_price(v)


class PromoCode(PromoCodeCreate):
    id: Optional[str] = Field(None, alias="_id")
    usage_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Menu item models (links products/combos from assortment to active menu)
class MenuItemCreate(BaseModel):
    item_type: str = "product"  # "product" or "combo"
    product_id: Optional[str] = None  # For products
    combo_id: Optional[str] = None    # For combos
    category_id: Optional[str] = None  # Override category (useful for combos)
    is_active: bool = True
    sort_order: int = 0


class MenuItem(MenuItemCreate):
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Delivery Zone models
class ZoneType(str, Enum):
    RADIUS = "radius"
    POLYGON = "polygon"


class DeliveryZoneCreate(BaseModel):
    name: str
    zone_type: ZoneType = ZoneType.RADIUS

    # Radius-specific fields
    radius_km: Optional[float] = Field(None, gt=0, le=50)
    center_lat: Optional[float] = Field(None, ge=-90, le=90)
    center_lng: Optional[float] = Field(None, ge=-180, le=180)

    # Polygon-specific fields
    custom_geometry: Optional[dict] = None

    # Common fields
    color: str = "#22c55e"
    delivery_fee: float = Field(..., ge=0)
    min_order_amount: float = Field(0, ge=0)
    free_delivery_threshold: Optional[float] = Field(None, ge=0)
    enabled: bool = True
    priority: int = Field(0, ge=0)

    @field_validator('delivery_fee', 'min_order_amount')
    @classmethod
    def round_zone_fees(cls, v):
        return round(v, 2)

    @field_validator('free_delivery_threshold')
    @classmethod
    def round_free_threshold(cls, v):
        if v is None:
            return v
        return round(v, 2)

    @field_validator('radius_km')
    @classmethod
    def validate_radius_for_radius_zones(cls, v, info):
        values = info.data
        if values.get('zone_type') == ZoneType.RADIUS and v is None:
            raise ValueError('radius_km is required for radius zones')
        return v

    @field_validator('custom_geometry')
    @classmethod
    def validate_geometry_for_polygon_zones(cls, v, info):
        values = info.data
        if values.get('zone_type') == ZoneType.POLYGON:
            if v is None:
                raise ValueError('custom_geometry is required for polygon zones')

            # Validate GeoJSON Polygon structure
            if not isinstance(v, dict):
                raise ValueError('custom_geometry must be a dict')

            if v.get('type') != 'Polygon':
                raise ValueError('custom_geometry must be a GeoJSON Polygon')

            coords = v.get('coordinates', [])
            if not coords or not isinstance(coords, list):
                raise ValueError('Polygon must have coordinates')

            if len(coords) < 1 or len(coords[0]) < 4:
                raise ValueError('Polygon must have at least 3 vertices')

            # Check maximum complexity (prevent DoS)
            if len(coords[0]) > 1000:
                raise ValueError('Polygon too complex (max 1000 vertices)')

            # Optional: Check coordinate bounds (Ukraine area check)
            for coord in coords[0]:
                if not isinstance(coord, list) or len(coord) < 2:
                    continue
                lng, lat = coord[0], coord[1]
                if not (22 <= lng <= 40 and 44 <= lat <= 52):
                    raise ValueError('Polygon coordinates outside expected area (Ukraine)')

        return v


class DeliveryZone(DeliveryZoneCreate):
    id: Optional[str] = Field(None, alias="_id")
    geometry: Optional[dict] = None  # GeoJSON Polygon
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Delivery Center models
class DeliveryCenterUpdate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    address: str = ""


class DeliveryCenter(DeliveryCenterUpdate):
    pass


# Zone detection models
class GeocodeRequest(BaseModel):
    address: str = Field(..., min_length=3)


class ZoneDetectionResult(BaseModel):
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    delivery_fee: float = 0
    min_order_amount: float = 0
    free_delivery_threshold: Optional[float] = None
    coordinates: Optional[dict] = None  # {"lat": x, "lng": y}
    available: bool = False
    message: str = ""


# Store Design models
class StorefrontBlock(BaseModel):
    id: str
    label: str
    enabled: bool = True
    sort_order: int = 0
    locked: bool = False


class ComponentSettings(BaseModel):
    productViewMode: str = "list"    # "list" | "grid"
    navPosition: str = "sidebar"     # "sidebar" | "top"
    cardStyle: str = "default"       # "default" | "horizontal" | "vertical-hero"


class BrandingSettings(BaseModel):
    accentColor: str = "#4CAF50"
    fontFamily: str = "system"       # "system"|"inter"|"roboto"|"open-sans"|"lato"|"nunito"
    borderRadius: str = "default"    # "default" | "rounded" | "sharp"


class AnnouncementSettings(BaseModel):
    text: str = ""
    bgColor: str = "#FFF3E0"
    textColor: str = "#E65100"


class HeroBannerSettings(BaseModel):
    imageUrl: str = ""
    altText: str = ""
    linkUrl: str = ""


class StoreInfoSettings(BaseModel):
    googleMapsEmbedUrl: str = ""
    showCopyButtons: bool = True
    infoPlacement: str = "sidebar"   # "sidebar" | "footer-section"


class StorefrontConfig(BaseModel):
    preset: str = "custom"           # "custom" | "clover" | "shaverma"
    layout: str = "sidebar-right"    # "sidebar-right" | "sidebar-left" | "footer"
    blocks: List[StorefrontBlock] = []
    components: ComponentSettings = ComponentSettings()
    branding: BrandingSettings = BrandingSettings()
    announcement: AnnouncementSettings = AnnouncementSettings()
    heroBanner: HeroBannerSettings = HeroBannerSettings()
    storeInfo: StoreInfoSettings = StoreInfoSettings()


# Page Builder V2 models
class PageElement(BaseModel):
    id: str
    type: str  # "text"|"image"|"menu"|"announcement"|"hours"|"address"|"phone"|"social"|"spacer"|"map"|"custom_html"
    label: str = ""
    visible: bool = True
    settings: dict = {}
    sort_order: int = 0


class PageColumn(BaseModel):
    id: str
    width: str = "1/1"  # "1/1"|"1/2"|"1/3"|"2/3"|"1/4"|"3/4"
    elements: List[PageElement] = []
    settings: dict = {}
    sort_order: int = 0


class PageRow(BaseModel):
    id: str
    columns: List[PageColumn] = []
    settings: dict = {}
    visible: bool = True
    sort_order: int = 0


class PageSection(BaseModel):
    id: str
    label: str = "Section"
    collapsed: bool = False
    visible: bool = True
    rows: List[PageRow] = []
    settings: dict = {}
    sort_order: int = 0


class PageBuilderConfig(BaseModel):
    version: int = 2
    sections: List[PageSection] = []
    branding: BrandingSettings = BrandingSettings()
    globalSettings: dict = {}


# Customer Category models
class CustomerCategoryCreate(BaseModel):
    name: str
    discount_percent: float = Field(0, ge=0, le=100)
    color: str = "#6366f1"
    description: str = ""
    is_active: bool = True


class CustomerCategory(CustomerCategoryCreate):
    id: Optional[str] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Customer models
class CustomerCreate(BaseModel):
    name: str = ""
    phone: str
    category_ids: List[str] = []
    notes: str = ""


class Customer(CustomerCreate):
    id: Optional[str] = Field(None, alias="_id")
    order_history: List[str] = []
    order_count: int = 0
    total_spent: float = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# Site Pages models
class ImageDisplayType(str, Enum):
    STANDARD = "standard"
    SLIDER = "slider"


class SitePageSection(BaseModel):
    id: str                        # UUID generated by client
    title: str = ""
    text: str = ""
    images: List[str] = []        # URL strings like /static/uploads/sections/...
    sort_order: int = 0


class SitePageCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    description: str = Field("", max_length=1000)
    image_display_type: ImageDisplayType = ImageDisplayType.STANDARD
    cover_image: str = ""
    categories: List[str] = []
    sections: List[SitePageSection] = []
    is_published: bool = True
    sort_order: int = 0


class SitePageUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=1000)
    image_display_type: Optional[ImageDisplayType] = None
    cover_image: Optional[str] = None
    categories: Optional[List[str]] = None
    sections: Optional[List[SitePageSection]] = None
    is_published: Optional[bool] = None
    sort_order: Optional[int] = None
