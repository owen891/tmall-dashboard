# 后端代码规范

## 1. FastAPI 项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # 应用入口
│   ├── config.py        # 配置
│   ├── database.py      # 数据库
│   ├── models/          # 数据模型
│   │   ├── __init__.py
│   │   └── product.py
│   ├── api/             # API 路由
│   │   ├── __init__.py
│   │   ├── products.py
│   │   └── dashboard.py
│   ├── schemas/         # Pydantic 模型
│   │   ├── __init__.py
│   │   └── product.py
│   └── utils/           # 工具函数
│       ├── __init__.py
│       └── helpers.py
├── requirements.txt
└── main.py
```

## 2. API 路由规范

### 2.1 路由定义

```python
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/api/products", tags=["商品管理"])

@router.get("/")
async def get_products(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="类目筛选"),
    status: Optional[str] = Query(None, description="状态筛选")
):
    """获取商品列表"""
    try:
        # 业务逻辑
        offset = (page - 1) * page_size
        products = Product.query.filter(...).limit(page_size).offset(offset).all()
        total = Product.query.count()
        
        return {
            "data": [p.to_dict() for p in products],
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except Exception as e:
        # 记录错误
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="获取数据失败")

@router.get("/{product_id}")
async def get_product(product_id: int):
    """获取单个商品"""
    product = Product.query.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product.to_dict()

@router.post("/")
async def create_product(product_data: ProductCreate):
    """创建商品"""
    try:
        product = Product(**product_data.dict())
        db.session.add(product)
        db.session.commit()
        return {"id": product.id, "message": "创建成功"}
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{product_id}")
async def update_product(product_id: int, product_data: ProductUpdate):
    """更新商品"""
    product = Product.query.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    try:
        for key, value in product_data.dict(exclude_unset=True).items():
            setattr(product, key, value)
        db.session.commit()
        return {"message": "更新成功"}
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{product_id}")
async def delete_product(product_id: int):
    """删除商品"""
    product = Product.query.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    
    try:
        db.session.delete(product)
        db.session.commit()
        return {"message": "删除成功"}
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
```

### 2.2 Query 参数规范

```python
# ✅ 正确
@router.get("/")
async def get_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    pass

# ❌ 错误：没有参数验证
@router.get("/")
async def get_list(page, page_size, category):
    pass
```

## 3. 数据库操作规范

### 3.1 模型定义

```python
from app import db
from datetime import datetime

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    category = db.Column(db.String(50), index=True)
    payment_amount = db.Column(db.Float, default=0)
    visitors = db.Column(db.Integer, default=0)
    conversion = db.Column(db.Float, default=0)
    roi = db.Column(db.Float, default=0)
    score = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active')
    list_date = db.Column(db.Date, default=datetime.now)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "payment_amount": self.payment_amount,
            "visitors": self.visitors,
            "conversion": self.conversion,
            "roi": self.roi,
            "score": self.score,
            "status": self.status,
            "list_date": self.list_date.isoformat() if self.list_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
```

### 3.2 数据库上下文

```python
# ✅ 正确：使用 app_context
with app.app_context():
    products = Product.query.all()
    db.session.commit()

# ❌ 错误：没有上下文
products = Product.query.all()
```

### 3.3 批量操作

```python
# ✅ 正确：批量插入
with app.app_context():
    products = []
    for item in data_list:
        product = Product(**item)
        products.append(product)
    db.session.bulk_save_objects(products)
    db.session.commit()

# ❌ 错误：逐条插入大量数据
with app.app_context():
    for item in data_list:
        product = Product(**item)
        db.session.add(product)
    db.session.commit()  # 最后提交一次
```

## 4. 错误处理规范

### 4.1 统一错误响应

```python
from fastapi import HTTPException
from fastapi.responses import JSONResponse

@router.get("/")
async def get_data():
    try:
        # 业务逻辑
        data = fetch_data()
        return {"data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=403, detail="权限不足")
    except Exception as e:
        # 记录错误日志
        print(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")
```

### 4.2 日志记录

```python
import logging

logger = logging.getLogger(__name__)

@router.get("/")
async def get_data():
    try:
        logger.info("Fetching data...")
        data = fetch_data()
        logger.info(f"Fetched {len(data)} items")
        return {"data": data}
    except Exception as e:
        logger.error(f"Error fetching data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="获取数据失败")
```

## 5. Pydantic 模型规范

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ProductBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    category: Optional[str] = None
    payment_amount: float = Field(default=0, ge=0)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = None
    payment_amount: Optional[float] = Field(None, ge=0)

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
```

## 6. API 文档规范

```python
@router.get("/", response_model=List[ProductResponse])
async def get_products(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(None, description="类目名称筛选"),
    status: Optional[str] = Query(None, description="商品状态筛选")
):
    """
    获取商品列表
    
    支持分页和筛选，返回商品列表和总数。
    
    - **page**: 页码，从1开始
    - **page_size**: 每页数量，最大100
    - **category**: 类目筛选，可选
    - **status**: 状态筛选，可选
    """
    pass
```

## 7. 安全规范

### 7.1 输入验证

```python
from pydantic import validator

class ProductCreate(BaseModel):
    title: str
    price: float
    
    @validator('title')
    def title_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('标题不能为空')
        return v.strip()
    
    @validator('price')
    def price_positive(cls, v):
        if v < 0:
            raise ValueError('价格必须大于0')
        return v
```

### 7.2 SQL 注入防护

```python
# ✅ 正确：使用参数化查询
products = Product.query.filter(
    Product.category == category
).all()

# ❌ 错误：字符串拼接 SQL
query = f"SELECT * FROM products WHERE category = '{category}'"
```

## 8. 性能优化

### 8.1 数据库索引

```python
class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = (
        db.Index('idx_category_status', 'category', 'status'),
        db.Index('idx_list_date', 'list_date'),
    )
```

### 8.2 缓存

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_category_options():
    """缓存类目选项"""
    categories = Category.query.all()
    return [(c.id, c.name) for c in categories]
```

## 9. 测试规范

```python
import pytest
from fastapi.testclient import TestClient
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_get_products(client):
    response = client.get("/api/products/")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data

def test_create_product(client):
    response = client.post("/api/products/", json={
        "title": "测试商品",
        "category": "测试类目"
    })
    assert response.status_code == 200
```
