"""
API 测试模块
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.core.database import Base, get_db


SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_check(self, client):
        """测试健康检查接口"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "project" in data


class TestProductsAPI:
    """产品API测试"""

    def test_get_products_list(self, client):
        """测试获取产品列表"""
        response = client.get("/api/products")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data["data"]

    def test_get_products_with_pagination(self, client):
        """测试分页获取产品"""
        response = client.get("/api/products?limit=10&offset=0")
        assert response.status_code == 200


class TestDashboardAPI:
    """仪表盘API测试"""

    def test_get_summary(self, client):
        """测试获取概览数据"""
        response = client.get("/api/dashboard/summary")
        assert response.status_code == 200


class TestKPIAPI:
    """KPI API测试"""

    def test_get_kpi_summary(self, client):
        """测试获取KPI概览"""
        response = client.get("/api/kpi/summary")
        assert response.status_code == 200
