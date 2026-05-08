from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List
from pydantic import BaseModel
from app.core.database import get_db
from app.models.command_tower import (
    ABTest, ABTestVariant, ABTestMetrics, ABTestAnalysis, SOPTemplate, CampaignProject
)
from app.schemas.common import ResponseModel
from datetime import datetime
import math


class ABTestCreate(BaseModel):
    test_name: str
    test_type: str = "landing_page"
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    significance_level: float = 0.95

router = APIRouter(prefix="/abtest-sop", tags=["A/B测试与SOP"])


@router.get("/tests", response_model=ResponseModel)
def get_ab_tests(
    status: Optional[str] = None,
    test_type: Optional[str] = None,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取A/B测试列表"""
    query = db.query(ABTest)
    if status:
        query = query.filter(ABTest.status == status)
    if test_type:
        query = query.filter(ABTest.test_type == test_type)
    
    total = query.count()
    tests = query.order_by(desc(ABTest.created_at)).offset(offset).limit(limit).all()
    
    result = []
    for test in tests:
        variants = db.query(ABTestVariant).filter(ABTestVariant.test_id == test.id).all()
        analysis = db.query(ABTestAnalysis).filter(ABTestAnalysis.test_id == test.id).first()
        
        result.append({
            "id": test.id,
            "test_name": test.test_name,
            "test_type": test.test_type,
            "status": test.status,
            "start_date": test.start_date,
            "end_date": test.end_date,
            "variant_count": len(variants),
            "has_winner": analysis.winner_variant if analysis else None,
            "is_significant": analysis.is_significant if analysis else False,
            "created_by": test.created_by
        })
    
    return ResponseModel(data={"tests": result, "total": total})


@router.get("/tests/{test_id}", response_model=ResponseModel)
def get_ab_test_detail(test_id: int, db: Session = Depends(get_db)):
    """获取A/B测试详情"""
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        return ResponseModel(code=404, message="测试不存在")
    
    variants = db.query(ABTestVariant).filter(ABTestVariant.test_id == test.id).all()
    analysis = db.query(ABTestAnalysis).filter(ABTestAnalysis.test_id == test.id).first()
    
    # 获取各变体的汇总数据
    variant_data = []
    for variant in variants:
        metrics = db.query(func.sum(ABTestMetrics.visitors).label("total_visitors"),
                          func.sum(ABTestMetrics.clicks).label("total_clicks"),
                          func.sum(ABTestMetrics.orders).label("total_orders"),
                          func.sum(ABTestMetrics.gmv).label("total_gmv"),
                          func.avg(ABTestMetrics.ctr).label("avg_ctr"),
                          func.avg(ABTestMetrics.conversion_rate).label("avg_conversion"),
                          func.avg(ABTestMetrics.roi).label("avg_roi")).filter(
            ABTestMetrics.variant_id == variant.id
        ).first()
        
        variant_data.append({
            "id": variant.id,
            "variant_name": variant.variant_name,
            "is_control": variant.is_control,
            "traffic_ratio": variant.traffic_ratio,
            "total_visitors": metrics.total_visitors or 0,
            "total_clicks": metrics.total_clicks or 0,
            "total_orders": metrics.total_orders or 0,
            "total_gmv": metrics.total_gmv or 0,
            "avg_ctr": metrics.avg_ctr or 0,
            "avg_conversion": metrics.avg_conversion or 0,
            "avg_roi": metrics.avg_roi or 0
        })
    
    return ResponseModel(data={
        "test": {
            "id": test.id,
            "test_name": test.test_name,
            "test_type": test.test_type,
            "description": test.description,
            "status": test.status,
            "start_date": test.start_date,
            "end_date": test.end_date,
            "significance_level": test.significance_level,
            "created_by": test.created_by
        },
        "variants": variant_data,
        "analysis": {
            "winner_variant": analysis.winner_variant,
            "is_significant": analysis.is_significant,
            "confidence_level": analysis.confidence_level,
            "uplift_percent": analysis.uplift_percent,
            "recommendations": analysis.recommendations
        } if analysis else None
    })


def calculate_statistical_significance(control_conversions, control_visitors,
                                      variant_conversions, variant_visitors):
    """计算统计显著性"""
    if control_visitors == 0 or variant_visitors == 0:
        return 0, False
    
    control_rate = control_conversions / control_visitors
    variant_rate = variant_conversions / variant_visitors
    
    # 简单Z检验
    if control_rate == variant_rate:
        return 0, False
    
    pooled_p = (control_conversions + variant_conversions) / (control_visitors + variant_visitors)
    pooled_se = math.sqrt(pooled_p * (1 - pooled_p) * (1/control_visitors + 1/variant_visitors))
    
    if pooled_se == 0:
        return 0, False
    
    z_score = (variant_rate - control_rate) / pooled_se
    
    # 简单判断是否显著
    is_significant = abs(z_score) > 1.96  # 95%置信度
    
    confidence = 0.95 if is_significant else 0.5
    
    return confidence, is_significant


@router.post("/tests/{test_id}/analyze", response_model=ResponseModel)
def analyze_ab_test(test_id: int, db: Session = Depends(get_db)):
    """分析A/B测试结果"""
    test = db.query(ABTest).filter(ABTest.id == test_id).first()
    if not test:
        return ResponseModel(code=404, message="测试不存在")
    
    variants = db.query(ABTestVariant).filter(ABTestVariant.test_id == test_id).all()
    if len(variants) < 2:
        return ResponseModel(code=400, message="需要至少两个变体")
    
    # 收集数据
    control_variant = None
    other_variants = []
    
    for v in variants:
        metrics = db.query(func.sum(ABTestMetrics.visitors).label("visitors"),
                          func.sum(ABTestMetrics.orders).label("orders")).filter(
            ABTestMetrics.variant_id == v.id
        ).first()
        
        v_data = {
            "id": v.id,
            "name": v.variant_name,
            "is_control": v.is_control,
            "visitors": metrics.visitors or 0,
            "orders": metrics.orders or 0,
            "conversion": (metrics.orders / metrics.visitors * 100) if metrics.visitors > 0 else 0
        }
        
        if v.is_control:
            control_variant = v_data
        else:
            other_variants.append(v_data)
    
    # 找出最优变体
    winner = None
    max_confidence = 0
    max_uplift = 0
    
    if control_variant:
        for variant in other_variants:
            confidence, is_significant = calculate_statistical_significance(
                control_variant["orders"], control_variant["visitors"],
                variant["orders"], variant["visitors"]
            )
            
            uplift = variant["conversion"] - control_variant["conversion"]
            
            if is_significant and uplift > max_uplift:
                winner = variant
                max_confidence = confidence
                max_uplift = uplift
    
    # 保存分析结果
    existing = db.query(ABTestAnalysis).filter(ABTestAnalysis.test_id == test_id).first()
    if existing:
        analysis = existing
    else:
        analysis = ABTestAnalysis(test_id=test_id)
    
    analysis.winner_variant = winner["name"] if winner else None
    analysis.is_significant = max_confidence >= 0.95
    analysis.confidence_level = max_confidence
    analysis.uplift_percent = max_uplift
    analysis.recommendations = (
        f"建议使用变体 {winner['name']}，可提升 {max_uplift:.1f}% 转化率"
        if winner else "暂无显著结果，建议延长测试时间"
    )
    
    if not existing:
        db.add(analysis)
    
    test.status = "finished"
    db.commit()
    
    return ResponseModel(data={
        "message": "分析完成",
        "winner": winner["name"] if winner else None,
        "is_significant": max_confidence >= 0.95,
        "uplift": max_uplift
    })


@router.get("/sop-templates", response_model=ResponseModel)
def get_sop_templates(
    template_type: Optional[str] = None,
    only_recommended: bool = False,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取SOP模板列表"""
    query = db.query(SOPTemplate)
    if template_type:
        query = query.filter(SOPTemplate.template_type == template_type)
    if only_recommended:
        query = query.filter(SOPTemplate.is_recommended == True)
    
    total = query.count()
    templates = query.order_by(desc(SOPTemplate.avg_effectiveness)).offset(offset).limit(limit).all()
    
    return ResponseModel(data={
        "templates": [{
            "id": t.id,
            "template_name": t.template_name,
            "template_type": t.template_type,
            "category": t.category,
            "description": t.description,
            "use_count": t.use_count,
            "avg_effectiveness": t.avg_effectiveness,
            "is_recommended": t.is_recommended,
            "tags": t.tags
        } for t in templates],
        "total": total
    })


@router.get("/sop-templates/{template_id}", response_model=ResponseModel)
def get_sop_template_detail(template_id: int, db: Session = Depends(get_db)):
    """获取SOP模板详情"""
    template = db.query(SOPTemplate).filter(SOPTemplate.id == template_id).first()
    if not template:
        return ResponseModel(code=404, message="模板不存在")
    
    return ResponseModel(data={
        "id": template.id,
        "template_name": template.template_name,
        "template_type": template.template_type,
        "category": template.category,
        "description": template.description,
        "content": template.content,
        "steps": template.steps,
        "use_count": template.use_count,
        "avg_effectiveness": template.avg_effectiveness,
        "tags": template.tags
    })


@router.get("/campaign-projects", response_model=ResponseModel)
def get_campaign_projects(
    status: Optional[str] = None,
    project_type: Optional[str] = None,
    limit: int = Query(50, description="返回数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db)
):
    """获取活动项目列表"""
    query = db.query(CampaignProject)
    if status:
        query = query.filter(CampaignProject.status == status)
    if project_type:
        query = query.filter(CampaignProject.project_type == project_type)
    
    total = query.count()
    projects = query.order_by(desc(CampaignProject.created_at)).offset(offset).limit(limit).all()
    
    return ResponseModel(data={
        "projects": [{
            "id": p.id,
            "project_name": p.project_name,
            "project_type": p.project_type,
            "status": p.status,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "target_gmv": p.target_gmv,
            "actual_gmv": p.actual_gmv,
            "owner": p.owner,
            "effectiveness_score": p.effectiveness_score
        } for p in projects],
        "total": total
    })


@router.post("/tests", response_model=ResponseModel)
def create_ab_test(
    test: ABTestCreate,
    db: Session = Depends(get_db)
):
    """创建A/B测试"""
    db_test = ABTest(
        test_name=test.test_name,
        test_type=test.test_type,
        description=test.description,
        start_date=test.start_date or datetime.now().strftime("%Y-%m-%d"),
        end_date=test.end_date,
        significance_level=test.significance_level,
        status="draft",
        created_by="system",
        created_at=datetime.now()
    )
    
    db.add(db_test)
    db.commit()
    db.refresh(db_test)
    
    return ResponseModel(data={"id": db_test.id, "message": "测试创建成功"})


@router.post("/sop-templates", response_model=ResponseModel)
def create_sop_template(
    template_name: str,
    template_type: str,
    description: str = "",
    content: str = "",
    db: Session = Depends(get_db)
):
    """创建SOP模板"""
    template = SOPTemplate(
        template_name=template_name,
        template_type=template_type,
        description=description,
        content=content,
        use_count=0,
        avg_effectiveness=0
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return ResponseModel(data={"id": template.id, "message": "模板创建成功"})

