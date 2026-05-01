from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_
from typing import List, Optional, Dict, Any
from datetime import date
from app.models import Product, WeeklyData, ProductTag, OperationAction, ProductNote, ProductHealth
from app.schemas import ProductCreate, ProductUpdate, WeeklyDataCreate, OperationActionCreate, ProductNoteCreate, ProductTagCreate


class ProductService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_products(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        category: Optional[str] = None,
        tier: Optional[str] = None,
        style: Optional[str] = None,
        scene: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc"
    ) -> tuple[List[Product], int]:
        query = self.db.query(Product)
        
        if search:
            query = query.filter(
                or_(
                    Product.title.contains(search),
                    Product.product_id.contains(search)
                )
            )
        
        if category:
            query = query.filter(Product.category == category)
        if tier:
            query = query.filter(Product.tier == tier)
        if style:
            query = query.filter(Product.style == style)
        if scene:
            query = query.filter(Product.scene == scene)
        
        total = query.count()
        
        if sort_by:
            if hasattr(Product, sort_by):
                sort_col = getattr(Product, sort_by)
                if sort_order == "desc":
                    query = query.order_by(desc(sort_col))
                else:
                    query = query.order_by(asc(sort_col))
            else:
                query = query.order_by(desc(Product.updated_at))
        else:
            query = query.order_by(desc(Product.updated_at))
        
        products = query.offset((page - 1) * page_size).limit(page_size).all()
        return products, total
    
    def get_product(self, product_id: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.product_id == product_id).first()
    
    def create_product(self, product_data: ProductCreate) -> Product:
        product = Product(**product_data.model_dump())
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product
    
    def update_product(self, product_id: str, product_data: ProductUpdate) -> Optional[Product]:
        product = self.get_product(product_id)
        if not product:
            return None
        
        update_data = product_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(product, key, value)
        
        self.db.commit()
        self.db.refresh(product)
        return product
    
    def get_weekly_data(
        self,
        product_id: str,
        week_start: Optional[date] = None
    ) -> Optional[WeeklyData]:
        query = self.db.query(WeeklyData).filter(WeeklyData.product_id == product_id)
        if week_start:
            query = query.filter(WeeklyData.week_start == week_start)
        else:
            query = query.order_by(desc(WeeklyData.week_start))
        return query.first()
    
    def get_all_weekly_data(self, product_id: str) -> List[WeeklyData]:
        return self.db.query(WeeklyData).filter(
            WeeklyData.product_id == product_id
        ).order_by(desc(WeeklyData.week_start)).all()
    
    def get_operations(self, product_id: str) -> List[OperationAction]:
        return self.db.query(OperationAction).filter(
            OperationAction.product_id == product_id
        ).order_by(desc(OperationAction.action_date)).all()
    
    def add_operation(self, action_data: OperationActionCreate) -> OperationAction:
        action = OperationAction(**action_data.model_dump())
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action
    
    def get_notes(self, product_id: str) -> List[ProductNote]:
        return self.db.query(ProductNote).filter(
            ProductNote.product_id == product_id
        ).order_by(desc(ProductNote.created_at)).all()
    
    def add_note(self, note_data: ProductNoteCreate) -> ProductNote:
        note = ProductNote(**note_data.model_dump())
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note
    
    def get_tags(self, product_id: str) -> List[ProductTag]:
        return self.db.query(ProductTag).filter(
            ProductTag.product_id == product_id
        ).all()
    
    def add_tag(self, tag_data: ProductTagCreate) -> ProductTag:
        existing = self.db.query(ProductTag).filter(
            ProductTag.product_id == tag_data.product_id,
            ProductTag.tag == tag_data.tag
        ).first()
        
        if existing:
            return existing
        
        tag = ProductTag(**tag_data.model_dump())
        self.db.add(tag)
        self.db.commit()
        self.db.refresh(tag)
        return tag
    
    def remove_tag(self, product_id: str, tag: str) -> bool:
        deleted = self.db.query(ProductTag).filter(
            ProductTag.product_id == product_id,
            ProductTag.tag == tag
        ).delete()
        self.db.commit()
        return deleted > 0
    
    def toggle_star(self, product_id: str) -> Optional[Product]:
        product = self.get_product(product_id)
        if not product:
            return None
        product.starred = not product.starred
        self.db.commit()
        self.db.refresh(product)
        return product
    
    def get_categories(self) -> List[str]:
        categories = self.db.query(Product.category).filter(
            Product.category.isnot(None)
        ).distinct().all()
        return [cat[0] for cat in categories if cat[0]]
    
    def get_tiers(self) -> List[str]:
        tiers = self.db.query(Product.tier).filter(
            Product.tier.isnot(None)
        ).distinct().all()
        return [t[0] for t in tiers if t[0]]
    
    def get_styles(self) -> List[str]:
        styles = self.db.query(Product.style).filter(
            Product.style.isnot(None)
        ).distinct().all()
        return [s[0] for s in styles if s[0]]
    
    def get_scenes(self) -> List[str]:
        scenes = self.db.query(Product.scene).filter(
            Product.scene.isnot(None)
        ).distinct().all()
        return [s[0] for s in scenes if s[0]]
    
    def get_dashboard_summary(self) -> Dict[str, Any]:
        latest_week = self.db.query(WeeklyData).order_by(
            desc(WeeklyData.week_start)
        ).first()
        
        if not latest_week:
            return {
                "total_products": self.db.query(Product).count(),
                "total_gmv": 0,
                "total_visitors": 0,
                "total_ad_spend": 0,
                "avg_roi": 0
            }
        
        week_start = latest_week.week_start
        
        week_data = self.db.query(WeeklyData).filter(
            WeeklyData.week_start == week_start
        ).all()
        
        total_gmv = sum(w.net_sales for w in week_data)
        total_visitors = sum(w.ipv for w in week_data)  # 用 ipv 代替 visitors
        total_ad_spend = sum(w.ad_spend for w in week_data)
        avg_roi = sum(w.ad_roi for w in week_data) / len(week_data) if week_data else 0  # 用 ad_roi 代替 total_roi
        
        return {
            "total_products": self.db.query(Product).count(),
            "total_gmv": total_gmv,
            "total_visitors": total_visitors,
            "total_ad_spend": total_ad_spend,
            "avg_roi": avg_roi,
            "week_start": week_start.isoformat() if week_start else None
        }
